package com.cmn.inuyasha.standalonepoc;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public class LoopbackService extends Service {
    private static final String TAG = "InuStandalonePOC";
    private volatile boolean running = false;
    private ServerSocket serverSocket;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!running) {
            running = true;
            if (Build.VERSION.SDK_INT >= 26) {
                NotificationManager nm = getSystemService(NotificationManager.class);
                nm.createNotificationChannel(new NotificationChannel("poc", "Local Server POC", NotificationManager.IMPORTANCE_LOW));
                Notification n = new Notification.Builder(this, "poc")
                    .setContentTitle("Inuyasha Local RPC POC")
                    .setContentText("127.0.0.1:18082 active")
                    .setSmallIcon(android.R.drawable.stat_sys_upload_done)
                    .build();
                startForeground(101, n);
            }
            new Thread(this::serveLoop, "LoopbackHTTP").start();
        }
        return START_STICKY;
    }

    private void serveLoop() {
        try {
            serverSocket = new ServerSocket(18082, 16, InetAddress.getByName("127.0.0.1"));
            Log.i(TAG, "BOUND_127_0_0_1_18082");
            while (running) {
                Socket client = serverSocket.accept();
                try {
                    byte[] body = "{\"Code\":0,\"Data\":{\"Server\":[{\"ServerID\":1,\"Address\":\"http://127.0.0.1:18082/client.aspx\"}]}}".getBytes(StandardCharsets.UTF_8);
                    String hdr = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                        + body.length + "\r\nConnection: close\r\n\r\n";
                    OutputStream os = client.getOutputStream();
                    os.write(hdr.getBytes(StandardCharsets.US_ASCII));
                    os.write(body);
                    os.flush();
                } finally {
                    client.close();
                }
            }
        } catch (Exception e) {
            if (running) Log.e(TAG, "serveLoop err", e);
        }
    }

    @Override
    public void onDestroy() {
        running = false;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
