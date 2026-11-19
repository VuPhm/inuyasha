package com.cmn.inuyasha.standalone;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

public final class LocalBackendService extends Service {
    private volatile boolean running = false;
    private Thread watchdogThread = null;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!running) {
            running = true;
            watchdogThread = new Thread(new Runnable() {
                @Override
                public void run() {
                    while (running) {
                        try {
                            LocalBackendManager.watchdogTick(getApplicationContext());
                            Thread.sleep(4000L);
                        } catch (InterruptedException ignored) {
                            break;
                        } catch (Throwable t) {
                            Log.w(LocalBackendManager.TAG, "Watchdog error: " + t);
                        }
                    }
                }
            }, "InuBackendWatchdog");
            watchdogThread.setDaemon(true);
            watchdogThread.start();
        }
        return START_NOT_STICKY;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        Log.i(LocalBackendManager.TAG, "onTaskRemoved -> stopping embedded backend & mirroring saves");
        running = false;
        LocalBackendManager.stopBackend(getApplicationContext());
        stopSelf();
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        running = false;
        if (watchdogThread != null) {
            watchdogThread.interrupt();
            watchdogThread = null;
        }
        LocalBackendManager.stopBackend(getApplicationContext());
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
