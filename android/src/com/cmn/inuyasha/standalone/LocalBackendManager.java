package com.cmn.inuyasha.standalone;

import android.content.Context;
import android.content.Intent;
import android.content.res.AssetManager;
import android.os.Looper;
import android.util.Log;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.RandomAccessFile;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class LocalBackendManager {
    public static final String TAG = "InuStandalone";
    public static final String HOST = "127.0.0.1";
    public static final int PORT = 18082;
    public static final String HEALTH_URL = "http://127.0.0.1:18082/health";

    private static final Object LOCK = new Object();
    private static Process backendProcess = null;
    private static volatile boolean activityActive = false;
    private static volatile long lastDestroyAtMs = 0L;
    private static volatile long lastHealthOkMs = 0L;
    private static volatile long lastLaunchStartMs = 0L;

    private LocalBackendManager() {}

    public static void onAppCreate(final Context context) {
        final Context appCtx = context.getApplicationContext();
        activityActive = true;
        new Thread(new Runnable() {
            @Override
            public void run() {
                ensureStarted(appCtx, 15000L);
            }
        }, "InuBackendPrewarm").start();
        try {
            appCtx.startService(new Intent(appCtx, LocalBackendService.class));
        } catch (Throwable t) {
            Log.w(TAG, "startService warning: " + t);
        }
    }

    public static void ensureStarted(Context context) {
        final Context appCtx = context.getApplicationContext();
        if (Looper.myLooper() == Looper.getMainLooper()) {
            activityActive = true;
            lastDestroyAtMs = 0L;
            if (isProcessAlive(backendProcess) && lastHealthOkMs > 0L && (System.currentTimeMillis() - lastHealthOkMs < 5000L)) {
                return;
            }
            Thread starter = new Thread(new Runnable() {
                @Override
                public void run() {
                    ensureStarted(appCtx, 15000L);
                }
            }, "InuBackendActivityStart");
            starter.setDaemon(true);
            starter.start();
            long waitStart = System.currentTimeMillis();
            try {
                while (System.currentTimeMillis() - waitStart < 3000L) {
                    if (lastHealthOkMs > 0L && lastHealthOkMs >= lastLaunchStartMs && isProcessAlive(backendProcess)) {
                        break;
                    }
                    if (!starter.isAlive()) {
                        break;
                    }
                    Thread.sleep(40L);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            return;
        }
        ensureStarted(appCtx, 12000L);
    }

    public static void ensureStarted(Context context, long maxWaitMs) {
        final Context appCtx = context.getApplicationContext();
        activityActive = true;
        lastDestroyAtMs = 0L;
        final long t0 = System.currentTimeMillis();
        final Process procToWait;
        final File stdoutToLog;
        final String saveDirPath;
        final String nativeLibDir;
        final long procLaunchMs;

        synchronized (LOCK) {
            long now = System.currentTimeMillis();
            if (isProcessAlive(backendProcess) && (now - lastHealthOkMs < 2500L || isLoopbackHealthy(350))) {
                lastHealthOkMs = System.currentTimeMillis();
                return;
            }
            if (!isProcessAlive(backendProcess) && isLoopbackHealthy(250)) {
                lastHealthOkMs = System.currentTimeMillis();
                Log.i(TAG, "Reusing existing healthy loopback backend on 127.0.0.1:" + PORT);
                return;
            }
            if (isProcessAlive(backendProcess) && lastLaunchStartMs > 0L && (now - lastLaunchStartMs < 25000L)) {
                procToWait = backendProcess;
                procLaunchMs = lastLaunchStartMs;
                File saveDir = getSaveDir(appCtx);
                stdoutToLog = new File(saveDir, "backend_stdout.log");
                saveDirPath = saveDir.getAbsolutePath();
                nativeLibDir = appCtx.getApplicationInfo().nativeLibraryDir;
            } else {
                Process startedProc = null;
                File stdoutFile = null;
                String resolvedSaveDir = "";
                String resolvedNativeDir = "";
                try {
                    File baseDir = new File(appCtx.getFilesDir(), "inubackend");
                    File pyDir = new File(baseDir, "py");
                    File serverDir = new File(baseDir, "server");
                    unpackAssetsIfNeeded(appCtx, baseDir, pyDir, serverDir);

                    File saveDir = getSaveDir(appCtx);
                    resolvedSaveDir = saveDir.getAbsolutePath();
                    File mirrorDir = getMirrorDir(appCtx);
                    restoreFromMirrorIfEmpty(saveDir, mirrorDir);

                    stopProcessLocked();

                    resolvedNativeDir = appCtx.getApplicationInfo().nativeLibraryDir;
                    File exeFile = new File(resolvedNativeDir, "libinubackend.so");
                    File emulatorPy = new File(serverDir, "emulator.py");
                    File traceFile = new File(saveDir, "rpc_trace.log");
                    stdoutFile = new File(saveDir, "backend_stdout.log");
                    File dynloadDir = new File(pyDir, "lib-dynload");
                    dynloadDir.mkdirs();

                    ProcessBuilder pb = new ProcessBuilder(
                        exeFile.getAbsolutePath(),
                        emulatorPy.getAbsolutePath(),
                        "--env", "dev",
                        "--host", HOST,
                        "--port", String.valueOf(PORT),
                        "--data-dir", resolvedSaveDir,
                        "--trace-path", traceFile.getAbsolutePath()
                    );
                    pb.directory(serverDir);
                    pb.redirectErrorStream(true);
                    pb.redirectOutput(ProcessBuilder.Redirect.appendTo(stdoutFile));

                    Map<String, String> env = pb.environment();
                    env.put("LD_LIBRARY_PATH", resolvedNativeDir);
                    env.put("INUYASHA_NATIVE_LIB_DIR", resolvedNativeDir);
                    env.put("INUYASHA_DYNLOAD_DIR", dynloadDir.getAbsolutePath());
                    env.put("PYTHONHOME", pyDir.getAbsolutePath());
                    env.put(
                        "PYTHONPATH",
                        new File(pyDir, "stdlib.zip").getAbsolutePath()
                            + ":" + dynloadDir.getAbsolutePath()
                            + ":" + serverDir.getAbsolutePath()
                    );
                    env.put("PYTHONNOUSERSITE", "1");
                    env.put("PYTHONDONTWRITEBYTECODE", "1");
                    env.put("INUYASHA_SEED_DIR", new File(serverDir, "seeds").getAbsolutePath());
                    env.put("INUYASHA_PUBLIC_BACKUP_PATH", "/sdcard/Download/InuYasha_Save_Backup.json");

                    startedProc = pb.start();
                    backendProcess = startedProc;
                    lastLaunchStartMs = System.currentTimeMillis();
                    lastHealthOkMs = 0L;
                } catch (Throwable t) {
                    Log.e(TAG, "Failed to start embedded backend", t);
                    return;
                }
                procToWait = startedProc;
                procLaunchMs = lastLaunchStartMs;
                stdoutToLog = stdoutFile;
                saveDirPath = resolvedSaveDir;
                nativeLibDir = resolvedNativeDir;
            }
        }

        boolean ready = false;
        final long waitStart = System.currentTimeMillis();
        try {
            while (System.currentTimeMillis() - waitStart < maxWaitMs) {
                long okMs = lastHealthOkMs;
                if (okMs > 0L && okMs >= procLaunchMs && isProcessAlive(procToWait)) {
                    ready = true;
                    break;
                }
                if (isLoopbackHealthy(300)) {
                    ready = true;
                    lastHealthOkMs = System.currentTimeMillis();
                    break;
                }
                if (!isProcessAlive(procToWait)) {
                    int exitCode = -1;
                    try {
                        if (procToWait != null) {
                            exitCode = procToWait.exitValue();
                        }
                    } catch (Throwable ignored) {}
                    String tail = readFileTail(stdoutToLog, 800);
                    Log.e(TAG, "BACKEND_EXITED_EARLY exit=" + exitCode + " tail=" + tail);
                    break;
                }
                Thread.sleep(60L);
            }
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
        long elapsed = System.currentTimeMillis() - t0;
        Log.i(
            TAG,
            "BACKEND_START ready=" + ready
                + " alive=" + isProcessAlive(procToWait)
                + " elapsed_ms=" + elapsed
                + " save_dir=" + saveDirPath
                + " native_lib=" + nativeLibDir
        );
    }

    public static void onActivityResume(final Context context) {
        final Context appCtx = context.getApplicationContext();
        activityActive = true;
        lastDestroyAtMs = 0L;
        new Thread(new Runnable() {
            @Override
            public void run() {
                ensureStarted(appCtx, 12000L);
            }
        }, "InuBackendResumeCheck").start();
    }

    public static void onActivityPause(final Context context) {
        final Context appCtx = context.getApplicationContext();
        new Thread(new Runnable() {
            @Override
            public void run() {
                mirrorSaves(appCtx);
            }
        }, "InuSaveMirrorPause").start();
    }

    public static void onActivityDestroy(final Context context) {
        final Context appCtx = context.getApplicationContext();
        activityActive = false;
        final long destroyStamp = System.currentTimeMillis();
        lastDestroyAtMs = destroyStamp;
        new Thread(new Runnable() {
            @Override
            public void run() {
                mirrorSaves(appCtx);
                try {
                    Thread.sleep(3500L);
                } catch (InterruptedException ignored) {}
                if (!activityActive && lastDestroyAtMs == destroyStamp) {
                    Log.i(TAG, "Activity closed; stopping embedded backend cleanly");
                    stopBackend(appCtx);
                }
            }
        }, "InuBackendShutdownGrace").start();
    }

    public static void watchdogTick(Context context) {
        final Context appCtx = context.getApplicationContext();
        if (activityActive) {
            boolean alive;
            synchronized (LOCK) {
                alive = isProcessAlive(backendProcess);
            }
            if (!alive && !isLoopbackHealthy(300)) {
                Log.w(TAG, "Watchdog detected stopped backend while game active; restarting");
                ensureStarted(appCtx, 15000L);
            }
        }
        mirrorSaves(appCtx);
    }

    public static void stopBackend(Context context) {
        if (context != null) {
            mirrorSaves(context.getApplicationContext());
        }
        synchronized (LOCK) {
            stopProcessLocked();
        }
    }

    private static void stopProcessLocked() {
        if (backendProcess != null) {
            try {
                backendProcess.destroy();
                for (int i = 0; i < 10; i++) {
                    if (!isProcessAlive(backendProcess)) {
                        break;
                    }
                    Thread.sleep(30L);
                }
                if (isProcessAlive(backendProcess)) {
                    backendProcess.destroyForcibly();
                }
            } catch (Throwable ignored) {
            } finally {
                backendProcess = null;
            }
        }
    }

    private static boolean isProcessAlive(Process p) {
        if (p == null) {
            return false;
        }
        try {
            p.exitValue();
            return false;
        } catch (IllegalThreadStateException running) {
            return true;
        }
    }

    public static boolean isLoopbackHealthy(final int timeoutMs) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            final boolean[] ok = new boolean[1];
            Thread t = new Thread(new Runnable() {
                @Override
                public void run() {
                    ok[0] = isLoopbackHealthyDirect(timeoutMs);
                }
            }, "InuHealthProbe");
            t.setDaemon(true);
            t.start();
            try {
                t.join(timeoutMs + 250L);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            return ok[0];
        }
        return isLoopbackHealthyDirect(timeoutMs);
    }

    private static boolean isLoopbackHealthyDirect(int timeoutMs) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(HEALTH_URL).openConnection();
            conn.setConnectTimeout(timeoutMs);
            conn.setReadTimeout(timeoutMs);
            conn.setRequestMethod("GET");
            int code = conn.getResponseCode();
            if (code == 200) {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    String line = br.readLine();
                    return line != null && line.contains("\"ok\"");
                }
            }
        } catch (Throwable ignored) {
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
        return false;
    }

    private static boolean isDirWritable(File dir) {
        try {
            if (!dir.exists() && !dir.mkdirs()) {
                return false;
            }
            if (!dir.isDirectory()) {
                return false;
            }
            File probe = new File(dir, ".write_probe_" + Thread.currentThread().getId());
            try (FileOutputStream fos = new FileOutputStream(probe)) {
                fos.write(0x20);
            }
            probe.delete();
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static String readFileTail(File f, int maxBytes) {
        if (f == null || !f.exists() || maxBytes <= 0) {
            return "";
        }
        try (RandomAccessFile raf = new RandomAccessFile(f, "r")) {
            long len = raf.length();
            if (len <= 0L) {
                return "";
            }
            long start = Math.max(0L, len - maxBytes);
            int toRead = (int) (len - start);
            raf.seek(start);
            byte[] buf = new byte[toRead];
            int offset = 0;
            while (offset < toRead) {
                int n = raf.read(buf, offset, toRead - offset);
                if (n < 0) {
                    break;
                }
                offset += n;
            }
            return new String(buf, 0, offset, StandardCharsets.UTF_8);
        } catch (Throwable ignored) {
            return "";
        }
    }

    public static File getSaveDir(Context ctx) {
        File ext = ctx.getExternalFilesDir(null);
        if (ext != null) {
            File extSaves = new File(ext, "saves");
            if (isDirWritable(extSaves)) {
                return extSaves;
            }
            Log.w(TAG, "External save dir not writable, falling back to internal filesDir: " + extSaves.getAbsolutePath());
        }
        File internalSaves = new File(ctx.getFilesDir(), "saves");
        if (!internalSaves.exists()) {
            internalSaves.mkdirs();
        }
        return internalSaves;
    }

    public static File getMirrorDir(Context ctx) {
        File dir = new File(ctx.getFilesDir(), "saves_mirror");
        if (!dir.exists()) {
            dir.mkdirs();
        }
        return dir;
    }

    private static void restoreFromMirrorIfEmpty(File saveDir, File mirrorDir) {
        try {
            File primaryNormal = new File(saveDir, "normal_profile.json");
            File mirrorNormal = new File(mirrorDir, "normal_profile.json");
            if (!primaryNormal.exists() && mirrorNormal.exists()) {
                Log.i(TAG, "Restoring saves from internal safety mirror into " + saveDir.getAbsolutePath());
                copyDirSaves(mirrorDir, saveDir);
            }
        } catch (Throwable t) {
            Log.w(TAG, "restoreFromMirrorIfEmpty warning: " + t);
        }
    }

    public static void mirrorSaves(Context ctx) {
        try {
            File saveDir = getSaveDir(ctx);
            File mirrorDir = getMirrorDir(ctx);
            if (new File(saveDir, "normal_profile.json").exists()) {
                copyDirSaves(saveDir, mirrorDir);
            }
        } catch (Throwable t) {
            Log.w(TAG, "mirrorSaves warning: " + t);
        }
    }

    private static void copyDirSaves(File srcDir, File dstDir) throws IOException {
        if (!srcDir.exists()) {
            return;
        }
        if (!dstDir.exists()) {
            dstDir.mkdirs();
        }
        File[] files = srcDir.listFiles();
        if (files == null) {
            return;
        }
        for (File f : files) {
            String name = f.getName();
            if (f.isDirectory()) {
                if ("backups".equals(name)) {
                    copyDirSaves(f, new File(dstDir, name));
                }
                continue;
            }
            if (name.startsWith(".")) {
                continue;
            }
            if (name.endsWith(".json") || name.endsWith(".jsonl")) {
                File target = new File(dstDir, name);
                if (!target.exists() || target.length() != f.length() || target.lastModified() < f.lastModified()) {
                    File tmp = new File(dstDir, "." + name + ".tmp");
                    copyFile(f, tmp);
                    tmp.renameTo(target);
                }
            }
        }
    }

    private static void unpackAssetsIfNeeded(Context ctx, File baseDir, File pyDir, File serverDir) throws IOException {
        AssetManager am = ctx.getAssets();
        String bundledVersion = readAssetText(am, "inubackend/version.txt").trim();
        File versionFile = new File(baseDir, "version.txt");
        File emulatorPy = new File(serverDir, "emulator.py");
        File stdlibZip = new File(pyDir, "stdlib.zip");
        if (versionFile.exists() && emulatorPy.exists() && stdlibZip.exists()) {
            String installedVersion = readFileText(versionFile).trim();
            if (bundledVersion.equals(installedVersion)) {
                return;
            }
        }
        Log.i(TAG, "Unpacking embedded Python stdlib & emulator server bundle (" + bundledVersion + ")");
        pyDir.mkdirs();
        serverDir.mkdirs();

        copyAssetToFile(am, "inubackend/stdlib.zip", stdlibZip);
        try (InputStream zisRaw = am.open("inubackend/server_bundle.zip");
             ZipInputStream zis = new ZipInputStream(zisRaw)) {
            ZipEntry entry;
            byte[] buf = new byte[32768];
            while ((entry = zis.getNextEntry()) != null) {
                File outFile = new File(serverDir, entry.getName());
                if (entry.isDirectory()) {
                    outFile.mkdirs();
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists()) {
                        parent.mkdirs();
                    }
                    File tmp = new File(outFile.getParentFile(), "." + outFile.getName() + ".tmp");
                    try (FileOutputStream fos = new FileOutputStream(tmp)) {
                        int n;
                        while ((n = zis.read(buf)) > 0) {
                            fos.write(buf, 0, n);
                        }
                    }
                    tmp.renameTo(outFile);
                }
                zis.closeEntry();
            }
        }
        writeFileText(versionFile, bundledVersion);
    }

    private static String readAssetText(AssetManager am, String assetPath) throws IOException {
        try (InputStream is = am.open(assetPath)) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = is.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            return new String(bos.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static void copyAssetToFile(AssetManager am, String assetPath, File destFile) throws IOException {
        File parent = destFile.getParentFile();
        if (parent != null && !parent.exists()) {
            parent.mkdirs();
        }
        File tmp = new File(parent, "." + destFile.getName() + ".tmp");
        try (InputStream is = am.open(assetPath);
             FileOutputStream fos = new FileOutputStream(tmp)) {
            byte[] buf = new byte[32768];
            int n;
            while ((n = is.read(buf)) > 0) {
                fos.write(buf, 0, n);
            }
        }
        tmp.renameTo(destFile);
    }

    private static void copyFile(File src, File dst) throws IOException {
        try (FileInputStream fis = new FileInputStream(src);
             FileOutputStream fos = new FileOutputStream(dst)) {
            byte[] buf = new byte[32768];
            int n;
            while ((n = fis.read(buf)) > 0) {
                fos.write(buf, 0, n);
            }
        }
    }

    private static String readFileText(File f) throws IOException {
        try (FileInputStream fis = new FileInputStream(f)) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = fis.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            return new String(bos.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static void writeFileText(File f, String text) throws IOException {
        File parent = f.getParentFile();
        if (parent != null && !parent.exists()) {
            parent.mkdirs();
        }
        try (FileOutputStream fos = new FileOutputStream(f)) {
            fos.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }
}
