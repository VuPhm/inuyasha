package com.cmn.inuyasha.standalonepoc;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final String TAG = "InuStandalonePOC";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView tv = new TextView(this);
        tv.setText("Starting 127.0.0.1:18082 loopback POC...");
        tv.setPadding(36, 72, 36, 36);
        setContentView(tv);

        startService(new Intent(this, LoopbackService.class));

        new Thread(() -> {
            long t0 = System.nanoTime();
            StringBuilder report = new StringBuilder();
            try {
                // Verify Android 12 rootless Scoped Storage save write/read
                File extDir = getExternalFilesDir(null);
                File saveFile = new File(extDir != null ? extDir : getFilesDir(), "save_poc.json");
                String sampleSave = "{\"player\":{\"Name\":\"OlinaHugh_POC\",\"Lv\":20},\"r\":\"7.6\"}";
                try (FileOutputStream fos = new FileOutputStream(saveFile)) {
                    fos.write(sampleSave.getBytes(StandardCharsets.UTF_8));
                }

                // Wait briefly for loopback bind and measure offline roundtrip latency
                String rpcReply = "";
                long rttNs = 0;
                for (int i = 0; i < 40; i++) {
                    try {
                        long reqStart = System.nanoTime();
                        HttpURLConnection conn = (HttpURLConnection) new URL("http://127.0.0.1:18082/API/ServerList_Client.ashx").openConnection();
                        conn.setConnectTimeout(500);
                        conn.setReadTimeout(500);
                        int code = conn.getResponseCode();
                        try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                            rpcReply = br.readLine();
                        }
                        rttNs = System.nanoTime() - reqStart;
                        if (code == 200) break;
                    } catch (Exception ignored) {
                        Thread.sleep(25);
                    }
                }
                long bindMs = (System.nanoTime() - t0) / 1_000_000L;
                double rttMs = rttNs / 1_000_000.0;
                String line = String.format(
                    "POC_OK bind_startup_ms=%d loopback_rtt_ms=%.2f save_path=%s save_bytes=%d reply=%s",
                    bindMs, rttMs, saveFile.getAbsolutePath(), saveFile.length(), rpcReply
                );
                Log.i(TAG, line);
                report.append(line);
            } catch (Exception e) {
                report.append("POC_ERR: ").append(e.toString());
                Log.e(TAG, "POC failed", e);
            }
            final String out = report.toString();
            runOnUiThread(() -> tv.setText(out));
        }).start();
    }
}
