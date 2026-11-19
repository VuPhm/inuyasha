.class public final Lcom/cmn/inuyasha/standalone/LocalBackendManager;
.super Ljava/lang/Object;
.source "LocalBackendManager.java"


# static fields
.field public static final HEALTH_URL:Ljava/lang/String; = "http://127.0.0.1:18082/health"

.field public static final HOST:Ljava/lang/String; = "127.0.0.1"

.field private static final LOCK:Ljava/lang/Object;

.field public static final PORT:I = 0x46a2

.field public static final TAG:Ljava/lang/String; = "InuStandalone"

.field private static volatile activityActive:Z

.field private static backendProcess:Ljava/lang/Process;

.field private static volatile lastDestroyAtMs:J

.field private static volatile lastHealthOkMs:J


# direct methods
.method static constructor <clinit>()V
    .locals 2

    .line 28
    new-instance v0, Ljava/lang/Object;

    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    .line 29
    const/4 v0, 0x0

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 30
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 31
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 32
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    return-void
.end method

.method private constructor <init>()V
    .locals 0

    .line 34
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method static synthetic access$000()Z
    .locals 1

    .line 22
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    return v0
.end method

.method static synthetic access$100()J
    .locals 2

    .line 22
    sget-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    return-wide v0
.end method

.method private static copyAssetToFile(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/io/File;)V
    .locals 4
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 398
    invoke-virtual {p2}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 399
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 400
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 402
    :cond_0
    new-instance v1, Ljava/io/File;

    new-instance v2, Ljava/lang/StringBuilder;

    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V

    const-string v3, "."

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    invoke-virtual {p2}, Ljava/io/File;->getName()Ljava/lang/String;

    move-result-object v3

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    const-string v3, ".tmp"

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v2

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 403
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 404
    :try_start_0
    new-instance p1, Ljava/io/FileOutputStream;

    invoke-direct {p1, v1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 405
    const v0, 0x8000

    :try_start_1
    new-array v0, v0, [B

    .line 407
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_1

    .line 408
    const/4 v3, 0x0

    invoke-virtual {p1, v0, v3, v2}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 410
    :cond_1
    :try_start_2
    invoke-virtual {p1}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    if-eqz p0, :cond_2

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 411
    :cond_2
    invoke-virtual {v1, p2}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 412
    return-void

    .line 403
    :catchall_0
    move-exception p2

    :try_start_3
    invoke-virtual {p1}, Ljava/io/FileOutputStream;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_1

    goto :goto_1

    :catchall_1
    move-exception p1

    :try_start_4
    invoke-virtual {p2, p1}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_1
    throw p2
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_2

    :catchall_2
    move-exception p1

    if-eqz p0, :cond_3

    :try_start_5
    invoke-virtual {p0}, Ljava/io/InputStream;->close()V
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_3

    goto :goto_2

    :catchall_3
    move-exception p0

    invoke-virtual {p1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :cond_3
    :goto_2
    throw p1
.end method

.method private static copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    .locals 11
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 308
    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_0

    .line 309
    return-void

    .line 311
    :cond_0
    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_1

    .line 312
    invoke-virtual {p1}, Ljava/io/File;->mkdirs()Z

    .line 314
    :cond_1
    invoke-virtual {p0}, Ljava/io/File;->listFiles()[Ljava/io/File;

    move-result-object p0

    .line 315
    if-nez p0, :cond_2

    .line 316
    return-void

    .line 318
    :cond_2
    array-length v0, p0

    const/4 v1, 0x0

    :goto_0
    if-ge v1, v0, :cond_8

    aget-object v2, p0, v1

    .line 319
    invoke-virtual {v2}, Ljava/io/File;->getName()Ljava/lang/String;

    move-result-object v3

    .line 320
    invoke-virtual {v2}, Ljava/io/File;->isDirectory()Z

    move-result v4

    if-eqz v4, :cond_3

    .line 321
    const-string v4, "backups"

    invoke-virtual {v4, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v4

    if-eqz v4, :cond_7

    .line 322
    new-instance v4, Ljava/io/File;

    invoke-direct {v4, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-static {v2, v4}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V

    goto :goto_1

    .line 326
    :cond_3
    const-string v4, "."

    invoke-virtual {v3, v4}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_4

    .line 327
    goto :goto_1

    .line 329
    :cond_4
    const-string v5, ".json"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-nez v5, :cond_5

    const-string v5, ".jsonl"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_7

    .line 330
    :cond_5
    new-instance v5, Ljava/io/File;

    invoke-direct {v5, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 331
    invoke-virtual {v5}, Ljava/io/File;->exists()Z

    move-result v6

    if-eqz v6, :cond_6

    invoke-virtual {v5}, Ljava/io/File;->length()J

    move-result-wide v6

    invoke-virtual {v2}, Ljava/io/File;->length()J

    move-result-wide v8

    cmp-long v10, v6, v8

    if-nez v10, :cond_6

    invoke-virtual {v5}, Ljava/io/File;->lastModified()J

    move-result-wide v6

    invoke-virtual {v2}, Ljava/io/File;->lastModified()J

    move-result-wide v8

    cmp-long v10, v6, v8

    if-gez v10, :cond_7

    .line 332
    :cond_6
    new-instance v6, Ljava/io/File;

    new-instance v7, Ljava/lang/StringBuilder;

    invoke-direct {v7}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v7, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v4

    invoke-virtual {v4, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v3

    const-string v4, ".tmp"

    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v3

    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v3

    invoke-direct {v6, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 333
    invoke-static {v2, v6}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyFile(Ljava/io/File;Ljava/io/File;)V

    .line 334
    invoke-virtual {v6, v5}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 318
    :cond_7
    :goto_1
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 338
    :cond_8
    return-void
.end method

.method private static copyFile(Ljava/io/File;Ljava/io/File;)V
    .locals 3
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 415
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 416
    :try_start_0
    new-instance p0, Ljava/io/FileOutputStream;

    invoke-direct {p0, p1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 417
    const p1, 0x8000

    :try_start_1
    new-array p1, p1, [B

    .line 419
    :goto_0
    invoke-virtual {v0, p1}, Ljava/io/FileInputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 420
    const/4 v2, 0x0

    invoke-virtual {p0, p1, v2, v1}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 422
    :cond_0
    :try_start_2
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 423
    return-void

    .line 415
    :catchall_0
    move-exception p1

    :try_start_3
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_1

    goto :goto_1

    :catchall_1
    move-exception p0

    :try_start_4
    invoke-virtual {p1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_1
    throw p1
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_2

    :catchall_2
    move-exception p0

    :try_start_5
    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_3

    goto :goto_2

    :catchall_3
    move-exception p1

    invoke-virtual {p0, p1}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_2
    throw p0
.end method

.method public static ensureStarted(Landroid/content/Context;)V
    .locals 26

    .line 53
    invoke-virtual/range {p0 .. p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object v0

    .line 54
    const/4 v1, 0x1

    sput-boolean v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 55
    const-wide/16 v2, 0x0

    sput-wide v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 56
    sget-object v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v2

    .line 57
    :try_start_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v3

    .line 58
    sget-object v5, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v5}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v5

    if-eqz v5, :cond_1

    sget-wide v5, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    sub-long/2addr v3, v5

    const-wide/16 v5, 0x9c4

    cmp-long v7, v3, v5

    if-ltz v7, :cond_0

    const/16 v3, 0x15e

    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v3

    if-eqz v3, :cond_1

    .line 59
    :cond_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 60
    monitor-exit v2

    return-void

    .line 62
    :cond_1
    sget-object v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v3

    if-nez v3, :cond_2

    const/16 v3, 0xfa

    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v3

    if-eqz v3, :cond_2

    .line 63
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 64
    const-string v0, "InuStandalone"

    const-string v1, "Reusing existing healthy loopback backend on 127.0.0.1:18082"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 65
    monitor-exit v2

    return-void

    .line 67
    :cond_2
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v3
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_1

    .line 69
    :try_start_1
    new-instance v5, Ljava/io/File;

    invoke-virtual {v0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object v6

    const-string v7, "inubackend"

    invoke-direct {v5, v6, v7}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 70
    new-instance v6, Ljava/io/File;

    const-string v7, "py"

    invoke-direct {v6, v5, v7}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 71
    new-instance v7, Ljava/io/File;

    const-string v8, "server"

    invoke-direct {v7, v5, v8}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 72
    invoke-static {v0, v5, v6, v7}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->unpackAssetsIfNeeded(Landroid/content/Context;Ljava/io/File;Ljava/io/File;Ljava/io/File;)V

    .line 74
    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v5

    .line 75
    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v8

    .line 76
    invoke-static {v5, v8}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->restoreFromMirrorIfEmpty(Ljava/io/File;Ljava/io/File;)V

    .line 78
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 80
    invoke-virtual {v0}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;

    move-result-object v0

    iget-object v0, v0, Landroid/content/pm/ApplicationInfo;->nativeLibraryDir:Ljava/lang/String;

    .line 81
    new-instance v8, Ljava/io/File;

    const-string v9, "libinubackend.so"

    invoke-direct {v8, v0, v9}, Ljava/io/File;-><init>(Ljava/lang/String;Ljava/lang/String;)V

    .line 82
    new-instance v9, Ljava/io/File;

    const-string v10, "emulator.py"

    invoke-direct {v9, v7, v10}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 83
    new-instance v10, Ljava/io/File;

    const-string v11, "rpc_trace.log"

    invoke-direct {v10, v5, v11}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 84
    new-instance v11, Ljava/io/File;

    const-string v12, "backend_stdout.log"

    invoke-direct {v11, v5, v12}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 85
    new-instance v12, Ljava/io/File;

    const-string v13, "lib-dynload"

    invoke-direct {v12, v6, v13}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 86
    invoke-virtual {v12}, Ljava/io/File;->mkdirs()Z

    .line 88
    new-instance v13, Ljava/lang/ProcessBuilder;

    .line 89
    invoke-virtual {v8}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v14

    .line 90
    invoke-virtual {v9}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v15

    const-string v16, "--env"

    const-string v17, "dev"

    const-string v18, "--host"

    const-string v19, "127.0.0.1"

    const-string v20, "--port"

    .line 93
    const/16 v8, 0x46a2

    invoke-static {v8}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v21

    const-string v22, "--data-dir"

    .line 94
    invoke-virtual {v5}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v23

    const-string v24, "--trace-path"

    .line 95
    invoke-virtual {v10}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v25

    filled-new-array/range {v14 .. v25}, [Ljava/lang/String;

    move-result-object v8

    invoke-direct {v13, v8}, Ljava/lang/ProcessBuilder;-><init>([Ljava/lang/String;)V

    .line 97
    invoke-virtual {v13, v7}, Ljava/lang/ProcessBuilder;->directory(Ljava/io/File;)Ljava/lang/ProcessBuilder;

    .line 98
    invoke-virtual {v13, v1}, Ljava/lang/ProcessBuilder;->redirectErrorStream(Z)Ljava/lang/ProcessBuilder;

    .line 99
    invoke-static {v11}, Ljava/lang/ProcessBuilder$Redirect;->appendTo(Ljava/io/File;)Ljava/lang/ProcessBuilder$Redirect;

    move-result-object v8

    invoke-virtual {v13, v8}, Ljava/lang/ProcessBuilder;->redirectOutput(Ljava/lang/ProcessBuilder$Redirect;)Ljava/lang/ProcessBuilder;

    .line 101
    invoke-virtual {v13}, Ljava/lang/ProcessBuilder;->environment()Ljava/util/Map;

    move-result-object v8

    .line 102
    const-string v9, "LD_LIBRARY_PATH"

    invoke-interface {v8, v9, v0}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 103
    const-string v9, "INUYASHA_NATIVE_LIB_DIR"

    invoke-interface {v8, v9, v0}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 104
    const-string v9, "INUYASHA_DYNLOAD_DIR"

    invoke-virtual {v12}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    invoke-interface {v8, v9, v10}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 105
    const-string v9, "PYTHONHOME"

    invoke-virtual {v6}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    invoke-interface {v8, v9, v10}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 106
    const-string v9, "PYTHONPATH"

    new-instance v10, Ljava/lang/StringBuilder;

    invoke-direct {v10}, Ljava/lang/StringBuilder;-><init>()V

    new-instance v11, Ljava/io/File;

    const-string v14, "stdlib.zip"

    invoke-direct {v11, v6, v14}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 108
    invoke-virtual {v11}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v6

    invoke-virtual {v10, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v6

    const-string v10, ":"

    invoke-virtual {v6, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v6

    .line 109
    invoke-virtual {v12}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    invoke-virtual {v6, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v6

    const-string v10, ":"

    invoke-virtual {v6, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v6

    .line 110
    invoke-virtual {v7}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    invoke-virtual {v6, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v6

    invoke-virtual {v6}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v6

    .line 106
    invoke-interface {v8, v9, v6}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 112
    const-string v6, "PYTHONNOUSERSITE"

    const-string v9, "1"

    invoke-interface {v8, v6, v9}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 113
    const-string v6, "PYTHONDONTWRITEBYTECODE"

    const-string v9, "1"

    invoke-interface {v8, v6, v9}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 114
    const-string v6, "INUYASHA_SEED_DIR"

    new-instance v9, Ljava/io/File;

    const-string v10, "seeds"

    invoke-direct {v9, v7, v10}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v9}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v7

    invoke-interface {v8, v6, v7}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 115
    const-string v6, "INUYASHA_PUBLIC_BACKUP_PATH"

    const-string v7, "/sdcard/Download/InuYasha_Save_Backup.json"

    invoke-interface {v8, v6, v7}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 117
    invoke-virtual {v13}, Ljava/lang/ProcessBuilder;->start()Ljava/lang/Process;

    move-result-object v6

    sput-object v6, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 118
    nop

    .line 119
    const/4 v6, 0x0

    const/4 v7, 0x0

    :goto_0
    const/16 v8, 0x5a

    if-ge v7, v8, :cond_5

    .line 120
    const/16 v8, 0x12c

    invoke-static {v8}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v8

    if-eqz v8, :cond_3

    .line 121
    nop

    .line 122
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v6

    sput-wide v6, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 123
    goto :goto_2

    .line 125
    :cond_3
    sget-object v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v8}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v8

    if-nez v8, :cond_4

    .line 126
    goto :goto_1

    .line 128
    :cond_4
    const-wide/16 v8, 0x2d

    invoke-static {v8, v9}, Ljava/lang/Thread;->sleep(J)V

    .line 119
    add-int/lit8 v7, v7, 0x1

    goto :goto_0

    .line 130
    :cond_5
    :goto_1
    const/4 v1, 0x0

    :goto_2
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v6

    sub-long/2addr v6, v3

    .line 131
    const-string v3, "InuStandalone"

    new-instance v4, Ljava/lang/StringBuilder;

    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V

    const-string v8, "BACKEND_START ready="

    invoke-virtual {v4, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v4

    invoke-virtual {v4, v1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v4, " elapsed_ms="

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v6, v7}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v4, " save_dir="

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    .line 135
    invoke-virtual {v5}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v4

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v4, " native_lib="

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    .line 131
    invoke-static {v3, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    .line 140
    goto :goto_3

    .line 138
    :catchall_0
    move-exception v0

    .line 139
    :try_start_2
    const-string v1, "InuStandalone"

    const-string v3, "Failed to start embedded backend"

    invoke-static {v1, v3, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    .line 141
    :goto_3
    monitor-exit v2

    .line 142
    return-void

    .line 141
    :catchall_1
    move-exception v0

    monitor-exit v2
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_1

    throw v0
.end method

.method public static getMirrorDir(Landroid/content/Context;)Ljava/io/File;
    .locals 2

    .line 275
    new-instance v0, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    const-string v1, "saves_mirror"

    invoke-direct {v0, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 276
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_0

    .line 277
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 279
    :cond_0
    return-object v0
.end method

.method public static getSaveDir(Landroid/content/Context;)Ljava/io/File;
    .locals 2

    .line 266
    const/4 v0, 0x0

    invoke-virtual {p0, v0}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    .line 267
    new-instance v1, Ljava/io/File;

    if-eqz v0, :cond_0

    goto :goto_0

    :cond_0
    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object v0

    :goto_0
    const-string p0, "saves"

    invoke-direct {v1, v0, p0}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 268
    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_1

    .line 269
    invoke-virtual {v1}, Ljava/io/File;->mkdirs()Z

    .line 271
    :cond_1
    return-object v1
.end method

.method public static isLoopbackHealthy(I)Z
    .locals 5

    .line 243
    nop

    .line 245
    const/4 v0, 0x0

    const/4 v1, 0x0

    :try_start_0
    new-instance v2, Ljava/net/URL;

    const-string v3, "http://127.0.0.1:18082/health"

    invoke-direct {v2, v3}, Ljava/net/URL;-><init>(Ljava/lang/String;)V

    invoke-virtual {v2}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;

    move-result-object v2

    check-cast v2, Ljava/net/HttpURLConnection;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_3

    .line 246
    :try_start_1
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V

    .line 247
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V

    .line 248
    const-string p0, "GET"

    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V

    .line 249
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getResponseCode()I

    move-result p0

    .line 250
    const/16 v1, 0xc8

    if-ne p0, v1, :cond_2

    .line 251
    new-instance p0, Ljava/io/BufferedReader;

    new-instance v1, Ljava/io/InputStreamReader;

    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;

    move-result-object v3

    sget-object v4, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, v3, v4}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/nio/charset/Charset;)V

    invoke-direct {p0, v1}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 252
    :try_start_2
    invoke-virtual {p0}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;

    move-result-object v1

    .line 253
    if-eqz v1, :cond_0

    const-string v3, "\"ok\""

    invoke-virtual {v1, v3}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v1
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_0

    if-eqz v1, :cond_0

    const/4 v1, 0x1

    goto :goto_0

    :cond_0
    const/4 v1, 0x0

    .line 254
    :goto_0
    :try_start_3
    invoke-virtual {p0}, Ljava/io/BufferedReader;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 258
    if-eqz v2, :cond_1

    .line 259
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 253
    :cond_1
    return v1

    .line 251
    :catchall_0
    move-exception v1

    :try_start_4
    invoke-virtual {p0}, Ljava/io/BufferedReader;->close()V
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_1

    goto :goto_1

    :catchall_1
    move-exception p0

    :try_start_5
    invoke-virtual {v1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_1
    throw v1
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_2

    .line 258
    :cond_2
    if-eqz v2, :cond_3

    .line 259
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    goto :goto_3

    .line 256
    :catchall_2
    move-exception p0

    move-object v1, v2

    goto :goto_2

    :catchall_3
    move-exception p0

    .line 258
    :goto_2
    if-eqz v1, :cond_3

    .line 259
    invoke-virtual {v1}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 262
    :cond_3
    :goto_3
    return v0
.end method

.method private static isProcessAlive(Ljava/lang/Process;)Z
    .locals 1

    .line 231
    const/4 v0, 0x0

    if-nez p0, :cond_0

    .line 232
    return v0

    .line 235
    :cond_0
    :try_start_0
    invoke-virtual {p0}, Ljava/lang/Process;->exitValue()I
    :try_end_0
    .catch Ljava/lang/IllegalThreadStateException; {:try_start_0 .. :try_end_0} :catch_0

    .line 236
    return v0

    .line 237
    :catch_0
    move-exception p0

    .line 238
    const/4 p0, 0x1

    return p0
.end method

.method public static mirrorSaves(Landroid/content/Context;)V
    .locals 3

    .line 297
    :try_start_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v0

    .line 298
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object p0

    .line 299
    new-instance v1, Ljava/io/File;

    const-string v2, "normal_profile.json"

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 300
    invoke-static {v0, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 304
    :cond_0
    goto :goto_0

    .line 302
    :catchall_0
    move-exception p0

    .line 303
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "mirrorSaves warning: "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p0

    const-string v0, "InuStandalone"

    invoke-static {v0, p0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 305
    :goto_0
    return-void
.end method

.method public static onActivityDestroy(Landroid/content/Context;)V
    .locals 4

    .line 167
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 168
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 169
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    .line 170
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 171
    new-instance v2, Ljava/lang/Thread;

    new-instance v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;

    invoke-direct {v3, p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;-><init>(Landroid/content/Context;J)V

    const-string p0, "InuBackendShutdownGrace"

    invoke-direct {v2, v3, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 183
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V

    .line 184
    return-void
.end method

.method public static onActivityPause(Landroid/content/Context;)V
    .locals 2

    .line 157
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 158
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;-><init>(Landroid/content/Context;)V

    const-string p0, "InuSaveMirrorPause"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 163
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 164
    return-void
.end method

.method public static onActivityResume(Landroid/content/Context;)V
    .locals 2

    .line 145
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 146
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 147
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 148
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;-><init>(Landroid/content/Context;)V

    const-string p0, "InuBackendResumeCheck"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 153
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 154
    return-void
.end method

.method public static onAppCreate(Landroid/content/Context;)V
    .locals 3

    .line 37
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 38
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 39
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;-><init>(Landroid/content/Context;)V

    const-string v2, "InuBackendPrewarm"

    invoke-direct {v0, v1, v2}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 44
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 46
    :try_start_0
    new-instance v0, Landroid/content/Intent;

    const-class v1, Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-direct {v0, p0, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 49
    goto :goto_0

    .line 47
    :catchall_0
    move-exception p0

    .line 48
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "startService warning: "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p0

    const-string v0, "InuStandalone"

    invoke-static {v0, p0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 50
    :goto_0
    return-void
.end method

.method private static readAssetText(Landroid/content/res/AssetManager;Ljava/lang/String;)Ljava/lang/String;
    .locals 3
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 386
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 387
    :try_start_0
    new-instance p1, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p1}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 388
    const/16 v0, 0x1000

    new-array v0, v0, [B

    .line 390
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 391
    const/4 v2, 0x0

    invoke-virtual {p1, v0, v2, v1}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 393
    :cond_0
    new-instance v0, Ljava/lang/String;

    invoke-virtual {p1}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p1

    sget-object v1, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v0, p1, v1}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 394
    if-eqz p0, :cond_1

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 393
    :cond_1
    return-object v0

    .line 386
    :catchall_0
    move-exception p1

    if-eqz p0, :cond_2

    :try_start_1
    invoke-virtual {p0}, Ljava/io/InputStream;->close()V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_1

    goto :goto_1

    :catchall_1
    move-exception p0

    invoke-virtual {p1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :cond_2
    :goto_1
    throw p1
.end method

.method private static readFileText(Ljava/io/File;)Ljava/lang/String;
    .locals 4
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 426
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 427
    :try_start_0
    new-instance p0, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p0}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 428
    const/16 v1, 0x1000

    new-array v1, v1, [B

    .line 430
    :goto_0
    invoke-virtual {v0, v1}, Ljava/io/FileInputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_0

    .line 431
    const/4 v3, 0x0

    invoke-virtual {p0, v1, v3, v2}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 433
    :cond_0
    new-instance v1, Ljava/lang/String;

    invoke-virtual {p0}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p0

    sget-object v2, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, p0, v2}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 434
    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 433
    return-object v1

    .line 426
    :catchall_0
    move-exception p0

    :try_start_1
    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_1

    goto :goto_1

    :catchall_1
    move-exception v0

    invoke-virtual {p0, v0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_1
    throw p0
.end method

.method private static restoreFromMirrorIfEmpty(Ljava/io/File;Ljava/io/File;)V
    .locals 4

    .line 284
    const-string v0, "InuStandalone"

    const-string v1, "normal_profile.json"

    :try_start_0
    new-instance v2, Ljava/io/File;

    invoke-direct {v2, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 285
    new-instance v3, Ljava/io/File;

    invoke-direct {v3, p1, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 286
    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    invoke-virtual {v3}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 287
    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "Restoring saves from internal safety mirror into "

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {p0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 288
    invoke-static {p1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 292
    :cond_0
    goto :goto_0

    .line 290
    :catchall_0
    move-exception p0

    .line 291
    new-instance p1, Ljava/lang/StringBuilder;

    invoke-direct {p1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "restoreFromMirrorIfEmpty warning: "

    invoke-virtual {p1, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p0

    invoke-static {v0, p0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 293
    :goto_0
    return-void
.end method

.method public static stopBackend(Landroid/content/Context;)V
    .locals 1

    .line 202
    if-eqz p0, :cond_0

    .line 203
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 205
    :cond_0
    sget-object p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter p0

    .line 206
    :try_start_0
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 207
    monitor-exit p0

    .line 208
    return-void

    .line 207
    :catchall_0
    move-exception v0

    monitor-exit p0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    throw v0
.end method

.method private static stopProcessLocked()V
    .locals 4

    .line 211
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    if-eqz v0, :cond_3

    .line 213
    const/4 v0, 0x0

    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroy()V

    .line 214
    const/4 v1, 0x0

    :goto_0
    const/16 v2, 0xa

    if-ge v1, v2, :cond_1

    .line 215
    sget-object v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v2

    if-nez v2, :cond_0

    .line 216
    goto :goto_1

    .line 218
    :cond_0
    const-wide/16 v2, 0x1e

    invoke-static {v2, v3}, Ljava/lang/Thread;->sleep(J)V

    .line 214
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 220
    :cond_1
    :goto_1
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    if-eqz v1, :cond_2

    .line 221
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroyForcibly()Ljava/lang/Process;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    goto :goto_2

    .line 223
    :catchall_0
    move-exception v1

    .line 225
    :cond_2
    :goto_2
    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 226
    nop

    .line 228
    :cond_3
    return-void
.end method

.method private static unpackAssetsIfNeeded(Landroid/content/Context;Ljava/io/File;Ljava/io/File;Ljava/io/File;)V
    .locals 7
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 341
    invoke-virtual {p0}, Landroid/content/Context;->getAssets()Landroid/content/res/AssetManager;

    move-result-object p0

    .line 342
    const-string v0, "inubackend/version.txt"

    invoke-static {p0, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readAssetText(Landroid/content/res/AssetManager;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v0

    .line 343
    new-instance v1, Ljava/io/File;

    const-string v2, "version.txt"

    invoke-direct {v1, p1, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 344
    new-instance p1, Ljava/io/File;

    const-string v2, "emulator.py"

    invoke-direct {p1, p3, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 345
    new-instance v2, Ljava/io/File;

    const-string v3, "stdlib.zip"

    invoke-direct {v2, p2, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 346
    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v3

    if-eqz v3, :cond_0

    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    .line 347
    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readFileText(Ljava/io/File;)Ljava/lang/String;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 348
    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result p1

    if-eqz p1, :cond_0

    .line 349
    return-void

    .line 352
    :cond_0
    new-instance p1, Ljava/lang/StringBuilder;

    invoke-direct {p1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v3, "Unpacking embedded Python stdlib & emulator server bundle ("

    invoke-virtual {p1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    const-string v3, ")"

    invoke-virtual {p1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    const-string v3, "InuStandalone"

    invoke-static {v3, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 353
    invoke-virtual {p2}, Ljava/io/File;->mkdirs()Z

    .line 354
    invoke-virtual {p3}, Ljava/io/File;->mkdirs()Z

    .line 356
    const-string p1, "inubackend/stdlib.zip"

    invoke-static {p0, p1, v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyAssetToFile(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/io/File;)V

    .line 357
    const-string p1, "inubackend/server_bundle.zip"

    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 358
    :try_start_0
    new-instance p1, Ljava/util/zip/ZipInputStream;

    invoke-direct {p1, p0}, Ljava/util/zip/ZipInputStream;-><init>(Ljava/io/InputStream;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_4

    .line 360
    const p2, 0x8000

    :try_start_1
    new-array p2, p2, [B

    .line 361
    :goto_0
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->getNextEntry()Ljava/util/zip/ZipEntry;

    move-result-object v2

    if-eqz v2, :cond_4

    .line 362
    new-instance v3, Ljava/io/File;

    invoke-virtual {v2}, Ljava/util/zip/ZipEntry;->getName()Ljava/lang/String;

    move-result-object v4

    invoke-direct {v3, p3, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 363
    invoke-virtual {v2}, Ljava/util/zip/ZipEntry;->isDirectory()Z

    move-result v2

    if-eqz v2, :cond_1

    .line 364
    invoke-virtual {v3}, Ljava/io/File;->mkdirs()Z

    goto :goto_2

    .line 366
    :cond_1
    invoke-virtual {v3}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v2

    .line 367
    if-eqz v2, :cond_2

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v4

    if-nez v4, :cond_2

    .line 368
    invoke-virtual {v2}, Ljava/io/File;->mkdirs()Z

    .line 370
    :cond_2
    new-instance v2, Ljava/io/File;

    invoke-virtual {v3}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v4

    new-instance v5, Ljava/lang/StringBuilder;

    invoke-direct {v5}, Ljava/lang/StringBuilder;-><init>()V

    const-string v6, "."

    invoke-virtual {v5, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v5

    invoke-virtual {v3}, Ljava/io/File;->getName()Ljava/lang/String;

    move-result-object v6

    invoke-virtual {v5, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v5

    const-string v6, ".tmp"

    invoke-virtual {v5, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v5

    invoke-virtual {v5}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v5

    invoke-direct {v2, v4, v5}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 371
    new-instance v4, Ljava/io/FileOutputStream;

    invoke-direct {v4, v2}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 373
    :goto_1
    :try_start_2
    invoke-virtual {p1, p2}, Ljava/util/zip/ZipInputStream;->read([B)I

    move-result v5

    if-lez v5, :cond_3

    .line 374
    const/4 v6, 0x0

    invoke-virtual {v4, p2, v6, v5}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_0

    goto :goto_1

    .line 376
    :cond_3
    :try_start_3
    invoke-virtual {v4}, Ljava/io/FileOutputStream;->close()V

    .line 377
    invoke-virtual {v2, v3}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 379
    :goto_2
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->closeEntry()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 380
    goto :goto_0

    .line 371
    :catchall_0
    move-exception p2

    :try_start_4
    invoke-virtual {v4}, Ljava/io/FileOutputStream;->close()V
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_1

    goto :goto_3

    :catchall_1
    move-exception p3

    :try_start_5
    invoke-virtual {p2, p3}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_3
    throw p2
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_2

    .line 381
    :cond_4
    :try_start_6
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->close()V
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_4

    if-eqz p0, :cond_5

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 382
    :cond_5
    invoke-static {v1, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->writeFileText(Ljava/io/File;Ljava/lang/String;)V

    .line 383
    return-void

    .line 357
    :catchall_2
    move-exception p2

    :try_start_7
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->close()V
    :try_end_7
    .catchall {:try_start_7 .. :try_end_7} :catchall_3

    goto :goto_4

    :catchall_3
    move-exception p1

    :try_start_8
    invoke-virtual {p2, p1}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_4
    throw p2
    :try_end_8
    .catchall {:try_start_8 .. :try_end_8} :catchall_4

    :catchall_4
    move-exception p1

    if-eqz p0, :cond_6

    :try_start_9
    invoke-virtual {p0}, Ljava/io/InputStream;->close()V
    :try_end_9
    .catchall {:try_start_9 .. :try_end_9} :catchall_5

    goto :goto_5

    :catchall_5
    move-exception p0

    invoke-virtual {p1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :cond_6
    :goto_5
    throw p1
.end method

.method public static watchdogTick(Landroid/content/Context;)V
    .locals 2

    .line 187
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 188
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    if-eqz v0, :cond_0

    .line 190
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v0

    .line 191
    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    .line 192
    monitor-exit v0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 193
    if-nez v1, :cond_0

    const/16 v0, 0x12c

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0

    if-nez v0, :cond_0

    .line 194
    const-string v0, "InuStandalone"

    const-string v1, "Watchdog detected stopped backend while game active; restarting"

    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 195
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;)V

    goto :goto_0

    .line 192
    :catchall_0
    move-exception p0

    :try_start_1
    monitor-exit v0
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    throw p0

    .line 198
    :cond_0
    :goto_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 199
    return-void
.end method

.method private static writeFileText(Ljava/io/File;Ljava/lang/String;)V
    .locals 2
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 438
    invoke-virtual {p0}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 439
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 440
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 442
    :cond_0
    new-instance v0, Ljava/io/FileOutputStream;

    invoke-direct {v0, p0}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V

    .line 443
    :try_start_0
    sget-object p0, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-virtual {p1, p0}, Ljava/lang/String;->getBytes(Ljava/nio/charset/Charset;)[B

    move-result-object p0

    invoke-virtual {v0, p0}, Ljava/io/FileOutputStream;->write([B)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 444
    invoke-virtual {v0}, Ljava/io/FileOutputStream;->close()V

    .line 445
    return-void

    .line 442
    :catchall_0
    move-exception p0

    :try_start_1
    invoke-virtual {v0}, Ljava/io/FileOutputStream;->close()V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_1

    goto :goto_0

    :catchall_1
    move-exception p1

    invoke-virtual {p0, p1}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_0
    throw p0
.end method
