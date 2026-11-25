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

.field private static volatile lastLaunchStartMs:J


# direct methods
.method static constructor <clinit>()V
    .locals 2

    .line 30
    new-instance v0, Ljava/lang/Object;

    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    .line 31
    const/4 v0, 0x0

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 32
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 33
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 34
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 35
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    return-void
.end method

.method private constructor <init>()V
    .locals 0

    .line 37
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method static synthetic access$000()Z
    .locals 1

    .line 24
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    return v0
.end method

.method static synthetic access$100()J
    .locals 2

    .line 24
    sget-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    return-wide v0
.end method

.method static synthetic access$200(I)Z
    .locals 0

    .line 24
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthyDirect(I)Z

    move-result p0

    return p0
.end method

.method private static copyAssetToFile(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/io/File;)V
    .locals 4
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 559
    invoke-virtual {p2}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 560
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 561
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 563
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

    .line 564
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 565
    :try_start_0
    new-instance p1, Ljava/io/FileOutputStream;

    invoke-direct {p1, v1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 566
    const v0, 0x8000

    :try_start_1
    new-array v0, v0, [B

    .line 568
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_1

    .line 569
    const/4 v3, 0x0

    invoke-virtual {p1, v0, v3, v2}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 571
    :cond_1
    :try_start_2
    invoke-virtual {p1}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    if-eqz p0, :cond_2

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 572
    :cond_2
    invoke-virtual {v1, p2}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 573
    return-void

    .line 564
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

    .line 469
    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_0

    .line 470
    return-void

    .line 472
    :cond_0
    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_1

    .line 473
    invoke-virtual {p1}, Ljava/io/File;->mkdirs()Z

    .line 475
    :cond_1
    invoke-virtual {p0}, Ljava/io/File;->listFiles()[Ljava/io/File;

    move-result-object p0

    .line 476
    if-nez p0, :cond_2

    .line 477
    return-void

    .line 479
    :cond_2
    array-length v0, p0

    const/4 v1, 0x0

    :goto_0
    if-ge v1, v0, :cond_8

    aget-object v2, p0, v1

    .line 480
    invoke-virtual {v2}, Ljava/io/File;->getName()Ljava/lang/String;

    move-result-object v3

    .line 481
    invoke-virtual {v2}, Ljava/io/File;->isDirectory()Z

    move-result v4

    if-eqz v4, :cond_3

    .line 482
    const-string v4, "backups"

    invoke-virtual {v4, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v4

    if-eqz v4, :cond_7

    .line 483
    new-instance v4, Ljava/io/File;

    invoke-direct {v4, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-static {v2, v4}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V

    goto :goto_1

    .line 487
    :cond_3
    const-string v4, "."

    invoke-virtual {v3, v4}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_4

    .line 488
    goto :goto_1

    .line 490
    :cond_4
    const-string v5, ".json"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-nez v5, :cond_5

    const-string v5, ".jsonl"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_7

    .line 491
    :cond_5
    new-instance v5, Ljava/io/File;

    invoke-direct {v5, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 492
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

    .line 493
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

    .line 494
    invoke-static {v2, v6}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyFile(Ljava/io/File;Ljava/io/File;)V

    .line 495
    invoke-virtual {v6, v5}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 479
    :cond_7
    :goto_1
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 499
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

    .line 576
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 577
    :try_start_0
    new-instance p0, Ljava/io/FileOutputStream;

    invoke-direct {p0, p1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 578
    const p1, 0x8000

    :try_start_1
    new-array p1, p1, [B

    .line 580
    :goto_0
    invoke-virtual {v0, p1}, Ljava/io/FileInputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 581
    const/4 v2, 0x0

    invoke-virtual {p0, p1, v2, v1}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 583
    :cond_0
    :try_start_2
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 584
    return-void

    .line 576
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
    .locals 10

    .line 56
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 57
    invoke-static {}, Landroid/os/Looper;->myLooper()Landroid/os/Looper;

    move-result-object v0

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    if-ne v0, v1, :cond_4

    .line 58
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 59
    const-wide/16 v1, 0x0

    sput-wide v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 60
    sget-object v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v3

    if-eqz v3, :cond_0

    sget-wide v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    cmp-long v5, v3, v1

    if-lez v5, :cond_0

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v3

    sget-wide v5, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    sub-long/2addr v3, v5

    const-wide/16 v5, 0x1388

    cmp-long v7, v3, v5

    if-gez v7, :cond_0

    .line 61
    return-void

    .line 63
    :cond_0
    new-instance v3, Ljava/lang/Thread;

    new-instance v4, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;

    invoke-direct {v4, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;-><init>(Landroid/content/Context;)V

    const-string p0, "InuBackendActivityStart"

    invoke-direct {v3, v4, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 69
    invoke-virtual {v3, v0}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 70
    invoke-virtual {v3}, Ljava/lang/Thread;->start()V

    .line 71
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v4

    .line 73
    :goto_0
    :try_start_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v6

    sub-long/2addr v6, v4

    const-wide/16 v8, 0xbb8

    cmp-long p0, v6, v8

    if-gez p0, :cond_3

    .line 74
    sget-wide v6, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    cmp-long p0, v6, v1

    if-lez p0, :cond_1

    sget-wide v6, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    sget-wide v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    cmp-long p0, v6, v8

    if-ltz p0, :cond_1

    sget-object p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result p0

    if-eqz p0, :cond_1

    .line 75
    goto :goto_1

    .line 77
    :cond_1
    invoke-virtual {v3}, Ljava/lang/Thread;->isAlive()Z

    move-result p0

    if-nez p0, :cond_2

    .line 78
    goto :goto_1

    .line 80
    :cond_2
    const-wide/16 v6, 0x28

    invoke-static {v6, v7}, Ljava/lang/Thread;->sleep(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_0

    .line 84
    :cond_3
    :goto_1
    goto :goto_2

    .line 82
    :catch_0
    move-exception p0

    .line 83
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/Thread;->interrupt()V

    .line 85
    :goto_2
    return-void

    .line 87
    :cond_4
    const-wide/16 v0, 0x2ee0

    invoke-static {p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;J)V

    .line 88
    return-void
.end method

.method public static ensureStarted(Landroid/content/Context;J)V
    .locals 26

    .line 91
    invoke-virtual/range {p0 .. p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object v0

    .line 92
    const/4 v1, 0x1

    sput-boolean v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 93
    const-wide/16 v2, 0x0

    sput-wide v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 94
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v4

    .line 101
    sget-object v6, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v6

    .line 102
    :try_start_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v7

    .line 103
    sget-object v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v9

    if-eqz v9, :cond_1

    sget-wide v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    sub-long v9, v7, v9

    const-wide/16 v11, 0x9c4

    cmp-long v13, v9, v11

    if-ltz v13, :cond_0

    const/16 v9, 0x15e

    invoke-static {v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v9

    if-eqz v9, :cond_1

    .line 104
    :cond_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 105
    monitor-exit v6

    return-void

    .line 107
    :cond_1
    sget-object v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v9

    if-nez v9, :cond_2

    const/16 v9, 0xfa

    invoke-static {v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v9

    if-eqz v9, :cond_2

    .line 108
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 109
    const-string v0, "InuStandalone"

    const-string v1, "Reusing existing healthy loopback backend on 127.0.0.1:18082"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 110
    monitor-exit v6

    return-void

    .line 112
    :cond_2
    sget-object v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v9

    if-eqz v9, :cond_3

    sget-wide v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    cmp-long v11, v9, v2

    if-lez v11, :cond_3

    sget-wide v9, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    sub-long/2addr v7, v9

    const-wide/16 v9, 0x61a8

    cmp-long v11, v7, v9

    if-gez v11, :cond_3

    .line 113
    sget-object v7, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 114
    sget-wide v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 115
    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v10

    .line 116
    new-instance v11, Ljava/io/File;

    const-string v12, "backend_stdout.log"

    invoke-direct {v11, v10, v12}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 117
    invoke-virtual {v10}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    .line 118
    invoke-virtual {v0}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;

    move-result-object v0

    iget-object v0, v0, Landroid/content/pm/ApplicationInfo;->nativeLibraryDir:Ljava/lang/String;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 119
    move-wide/from16 v24, v2

    move-object v2, v0

    goto/16 :goto_0

    .line 120
    :cond_3
    nop

    .line 121
    nop

    .line 122
    nop

    .line 123
    nop

    .line 125
    :try_start_1
    new-instance v7, Ljava/io/File;

    invoke-virtual {v0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object v8

    const-string v9, "inubackend"

    invoke-direct {v7, v8, v9}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 126
    new-instance v8, Ljava/io/File;

    const-string v9, "py"

    invoke-direct {v8, v7, v9}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 127
    new-instance v9, Ljava/io/File;

    const-string v10, "server"

    invoke-direct {v9, v7, v10}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 128
    invoke-static {v0, v7, v8, v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->unpackAssetsIfNeeded(Landroid/content/Context;Ljava/io/File;Ljava/io/File;Ljava/io/File;)V

    .line 130
    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v7

    .line 131
    invoke-virtual {v7}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v19

    .line 132
    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v10

    .line 133
    invoke-static {v7, v10}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->restoreFromMirrorIfEmpty(Ljava/io/File;Ljava/io/File;)V

    .line 135
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 137
    invoke-virtual {v0}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;

    move-result-object v0

    iget-object v0, v0, Landroid/content/pm/ApplicationInfo;->nativeLibraryDir:Ljava/lang/String;

    .line 138
    new-instance v10, Ljava/io/File;

    const-string v11, "libinubackend.so"

    invoke-direct {v10, v0, v11}, Ljava/io/File;-><init>(Ljava/lang/String;Ljava/lang/String;)V

    .line 139
    new-instance v11, Ljava/io/File;

    const-string v12, "emulator.py"

    invoke-direct {v11, v9, v12}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 140
    new-instance v12, Ljava/io/File;

    const-string v13, "rpc_trace.log"

    invoke-direct {v12, v7, v13}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 141
    new-instance v13, Ljava/io/File;

    const-string v14, "backend_stdout.log"

    invoke-direct {v13, v7, v14}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 142
    new-instance v7, Ljava/io/File;

    const-string v14, "lib-dynload"

    invoke-direct {v7, v8, v14}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 143
    invoke-virtual {v7}, Ljava/io/File;->mkdirs()Z

    .line 145
    new-instance v14, Ljava/lang/ProcessBuilder;

    .line 146
    invoke-virtual {v10}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v10

    .line 147
    invoke-virtual {v11}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v11

    move-object v15, v12

    const-string v12, "--env"

    move-object/from16 v16, v13

    const-string v13, "dev"

    move-object/from16 v17, v14

    const-string v14, "--host"

    move-object/from16 v18, v15

    const-string v15, "127.0.0.1"

    move-object/from16 v20, v16

    const-string v16, "--port"

    .line 150
    const/16 v21, 0x46a2

    invoke-static/range {v21 .. v21}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v21

    move-object/from16 v22, v18

    const-string v18, "--data-dir"

    move-object/from16 v23, v20

    const-string v20, "--trace-path"

    .line 152
    invoke-virtual/range {v22 .. v22}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v22

    move-wide/from16 v24, v2

    move-object/from16 v2, v17

    move-object/from16 v17, v21

    move-object/from16 v21, v22

    filled-new-array/range {v10 .. v21}, [Ljava/lang/String;

    move-result-object v3

    invoke-direct {v2, v3}, Ljava/lang/ProcessBuilder;-><init>([Ljava/lang/String;)V

    .line 154
    invoke-virtual {v2, v9}, Ljava/lang/ProcessBuilder;->directory(Ljava/io/File;)Ljava/lang/ProcessBuilder;

    .line 155
    invoke-virtual {v2, v1}, Ljava/lang/ProcessBuilder;->redirectErrorStream(Z)Ljava/lang/ProcessBuilder;

    .line 156
    invoke-static/range {v23 .. v23}, Ljava/lang/ProcessBuilder$Redirect;->appendTo(Ljava/io/File;)Ljava/lang/ProcessBuilder$Redirect;

    move-result-object v3

    invoke-virtual {v2, v3}, Ljava/lang/ProcessBuilder;->redirectOutput(Ljava/lang/ProcessBuilder$Redirect;)Ljava/lang/ProcessBuilder;

    .line 158
    invoke-virtual {v2}, Ljava/lang/ProcessBuilder;->environment()Ljava/util/Map;

    move-result-object v3

    .line 159
    const-string v10, "LD_LIBRARY_PATH"

    invoke-interface {v3, v10, v0}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 160
    const-string v10, "INUYASHA_NATIVE_LIB_DIR"

    invoke-interface {v3, v10, v0}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 161
    const-string v10, "INUYASHA_DYNLOAD_DIR"

    invoke-virtual {v7}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v11

    invoke-interface {v3, v10, v11}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 162
    const-string v10, "PYTHONHOME"

    invoke-virtual {v8}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v11

    invoke-interface {v3, v10, v11}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 163
    const-string v10, "PYTHONPATH"

    new-instance v11, Ljava/lang/StringBuilder;

    invoke-direct {v11}, Ljava/lang/StringBuilder;-><init>()V

    new-instance v12, Ljava/io/File;

    const-string v13, "stdlib.zip"

    invoke-direct {v12, v8, v13}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 165
    invoke-virtual {v12}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v8

    invoke-virtual {v11, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v8

    const-string v11, ":"

    invoke-virtual {v8, v11}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v8

    .line 166
    invoke-virtual {v7}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v7

    invoke-virtual {v8, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v7

    const-string v8, ":"

    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v7

    .line 167
    invoke-virtual {v9}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v8

    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v7

    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v7

    .line 163
    invoke-interface {v3, v10, v7}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 169
    const-string v7, "PYTHONNOUSERSITE"

    const-string v8, "1"

    invoke-interface {v3, v7, v8}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 170
    const-string v7, "PYTHONDONTWRITEBYTECODE"

    const-string v8, "1"

    invoke-interface {v3, v7, v8}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 171
    const-string v7, "INUYASHA_SEED_DIR"

    new-instance v8, Ljava/io/File;

    const-string v10, "seeds"

    invoke-direct {v8, v9, v10}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v8}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v8

    invoke-interface {v3, v7, v8}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 172
    const-string v7, "INUYASHA_PUBLIC_BACKUP_PATH"

    const-string v8, "/sdcard/Download/InuYasha_Save_Backup.json"

    invoke-interface {v3, v7, v8}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 174
    invoke-virtual {v2}, Ljava/lang/ProcessBuilder;->start()Ljava/lang/Process;

    move-result-object v7

    .line 175
    sput-object v7, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 176
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v2

    sput-wide v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 177
    sput-wide v24, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_1

    .line 181
    nop

    .line 182
    nop

    .line 183
    :try_start_2
    sget-wide v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 184
    nop

    .line 185
    nop

    .line 186
    move-object/from16 v10, v19

    move-object/from16 v11, v23

    move-object v2, v0

    .line 188
    :goto_0
    monitor-exit v6
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    .line 190
    nop

    .line 191
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v12

    .line 193
    :goto_1
    const/4 v3, 0x0

    :try_start_3
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v14

    sub-long/2addr v14, v12

    cmp-long v0, v14, p1

    if-gez v0, :cond_8

    .line 194
    sget-wide v14, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 195
    cmp-long v0, v14, v24

    if-lez v0, :cond_4

    cmp-long v0, v14, v8

    if-ltz v0, :cond_4

    invoke-static {v7}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0

    if-eqz v0, :cond_4

    .line 196
    nop

    .line 197
    goto :goto_4

    .line 199
    :cond_4
    const/16 v0, 0x12c

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0
    :try_end_3
    .catch Ljava/lang/InterruptedException; {:try_start_3 .. :try_end_3} :catch_1

    if-eqz v0, :cond_5

    .line 200
    nop

    .line 201
    :try_start_4
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v8

    sput-wide v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J
    :try_end_4
    .catch Ljava/lang/InterruptedException; {:try_start_4 .. :try_end_4} :catch_0

    .line 202
    goto :goto_4

    .line 217
    :catch_0
    move-exception v0

    goto :goto_5

    .line 204
    :cond_5
    :try_start_5
    invoke-static {v7}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0
    :try_end_5
    .catch Ljava/lang/InterruptedException; {:try_start_5 .. :try_end_5} :catch_1

    if-nez v0, :cond_7

    .line 205
    nop

    .line 207
    const/4 v1, -0x1

    if-eqz v7, :cond_6

    .line 208
    :try_start_6
    invoke-virtual {v7}, Ljava/lang/Process;->exitValue()I

    move-result v1
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_0

    goto :goto_2

    .line 210
    :catchall_0
    move-exception v0

    :cond_6
    :goto_2
    nop

    .line 211
    const/16 v0, 0x320

    :try_start_7
    invoke-static {v11, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readFileTail(Ljava/io/File;I)Ljava/lang/String;

    move-result-object v0

    .line 212
    const-string v6, "InuStandalone"

    new-instance v8, Ljava/lang/StringBuilder;

    invoke-direct {v8}, Ljava/lang/StringBuilder;-><init>()V

    const-string v9, "BACKEND_EXITED_EARLY exit="

    invoke-virtual {v8, v9}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v8

    invoke-virtual {v8, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v8, " tail="

    invoke-virtual {v1, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v6, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    .line 213
    goto :goto_3

    .line 215
    :cond_7
    const-wide/16 v14, 0x3c

    invoke-static {v14, v15}, Ljava/lang/Thread;->sleep(J)V
    :try_end_7
    .catch Ljava/lang/InterruptedException; {:try_start_7 .. :try_end_7} :catch_1

    .line 216
    goto :goto_1

    .line 219
    :cond_8
    :goto_3
    const/4 v1, 0x0

    :goto_4
    goto :goto_6

    .line 217
    :catch_1
    move-exception v0

    const/4 v1, 0x0

    .line 218
    :goto_5
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Thread;->interrupt()V

    .line 220
    :goto_6
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v8

    sub-long/2addr v8, v4

    .line 221
    const-string v0, "InuStandalone"

    new-instance v3, Ljava/lang/StringBuilder;

    invoke-direct {v3}, Ljava/lang/StringBuilder;-><init>()V

    const-string v4, "BACKEND_START ready="

    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v3

    invoke-virtual {v3, v1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v3, " alive="

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    .line 224
    invoke-static {v7}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v3

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v3, " elapsed_ms="

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v8, v9}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v3, " save_dir="

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v3, " native_lib="

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    .line 221
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 229
    return-void

    .line 178
    :catchall_1
    move-exception v0

    .line 179
    :try_start_8
    const-string v1, "InuStandalone"

    const-string v2, "Failed to start embedded backend"

    invoke-static {v1, v2, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    .line 180
    monitor-exit v6

    return-void

    .line 188
    :catchall_2
    move-exception v0

    monitor-exit v6
    :try_end_8
    .catchall {:try_start_8 .. :try_end_8} :catchall_2

    throw v0
.end method

.method public static getMirrorDir(Landroid/content/Context;)Ljava/io/File;
    .locals 2

    .line 436
    new-instance v0, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    const-string v1, "saves_mirror"

    invoke-direct {v0, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 437
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_0

    .line 438
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 440
    :cond_0
    return-object v0
.end method

.method public static getSaveDir(Landroid/content/Context;)Ljava/io/File;
    .locals 4

    .line 420
    const/4 v0, 0x0

    invoke-virtual {p0, v0}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    .line 421
    const-string v1, "saves"

    if-eqz v0, :cond_1

    .line 422
    new-instance v2, Ljava/io/File;

    invoke-direct {v2, v0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 423
    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isDirWritable(Ljava/io/File;)Z

    move-result v0

    if-eqz v0, :cond_0

    .line 424
    return-object v2

    .line 426
    :cond_0
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v3, "External save dir not writable, falling back to internal filesDir: "

    invoke-virtual {v0, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v2}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v0, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v2, "InuStandalone"

    invoke-static {v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 428
    :cond_1
    new-instance v0, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    invoke-direct {v0, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 429
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_2

    .line 430
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 432
    :cond_2
    return-object v0
.end method

.method private static isDirWritable(Ljava/io/File;)Z
    .locals 5

    .line 375
    const/4 v0, 0x0

    :try_start_0
    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    invoke-virtual {p0}, Ljava/io/File;->mkdirs()Z

    move-result v1

    if-nez v1, :cond_0

    .line 376
    return v0

    .line 378
    :cond_0
    invoke-virtual {p0}, Ljava/io/File;->isDirectory()Z

    move-result v1

    if-nez v1, :cond_1

    .line 379
    return v0

    .line 381
    :cond_1
    new-instance v1, Ljava/io/File;

    new-instance v2, Ljava/lang/StringBuilder;

    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V

    const-string v3, ".write_probe_"

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object v3

    invoke-virtual {v3}, Ljava/lang/Thread;->getId()J

    move-result-wide v3

    invoke-virtual {v2, v3, v4}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    move-result-object v2

    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v2

    invoke-direct {v1, p0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 382
    new-instance p0, Ljava/io/FileOutputStream;

    invoke-direct {p0, v1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 383
    const/16 v2, 0x20

    :try_start_1
    invoke-virtual {p0, v2}, Ljava/io/FileOutputStream;->write(I)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    .line 384
    :try_start_2
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V

    .line 385
    invoke-virtual {v1}, Ljava/io/File;->delete()Z
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    .line 386
    const/4 p0, 0x1

    return p0

    .line 382
    :catchall_0
    move-exception v1

    :try_start_3
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_1

    goto :goto_0

    :catchall_1
    move-exception p0

    :try_start_4
    invoke-virtual {v1, p0}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_0
    throw v1
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_2

    .line 387
    :catchall_2
    move-exception p0

    .line 388
    return v0
.end method

.method public static isLoopbackHealthy(I)Z
    .locals 7

    .line 330
    invoke-static {}, Landroid/os/Looper;->myLooper()Landroid/os/Looper;

    move-result-object v0

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    if-ne v0, v1, :cond_0

    .line 331
    const/4 v0, 0x1

    new-array v1, v0, [Z

    .line 332
    new-instance v2, Ljava/lang/Thread;

    new-instance v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager$6;

    invoke-direct {v3, v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$6;-><init>([ZI)V

    const-string v4, "InuHealthProbe"

    invoke-direct {v2, v3, v4}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 338
    invoke-virtual {v2, v0}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 339
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V

    .line 341
    int-to-long v3, p0

    const-wide/16 v5, 0xfa

    add-long/2addr v3, v5

    :try_start_0
    invoke-virtual {v2, v3, v4}, Ljava/lang/Thread;->join(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0

    .line 344
    goto :goto_0

    .line 342
    :catch_0
    move-exception p0

    .line 343
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/Thread;->interrupt()V

    .line 345
    :goto_0
    const/4 p0, 0x0

    aget-boolean p0, v1, p0

    return p0

    .line 347
    :cond_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthyDirect(I)Z

    move-result p0

    return p0
.end method

.method private static isLoopbackHealthyDirect(I)Z
    .locals 5

    .line 351
    nop

    .line 353
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

    .line 354
    :try_start_1
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V

    .line 355
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V

    .line 356
    const-string p0, "GET"

    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V

    .line 357
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getResponseCode()I

    move-result p0

    .line 358
    const/16 v1, 0xc8

    if-ne p0, v1, :cond_2

    .line 359
    new-instance p0, Ljava/io/BufferedReader;

    new-instance v1, Ljava/io/InputStreamReader;

    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;

    move-result-object v3

    sget-object v4, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, v3, v4}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/nio/charset/Charset;)V

    invoke-direct {p0, v1}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 360
    :try_start_2
    invoke-virtual {p0}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;

    move-result-object v1

    .line 361
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

    .line 362
    :goto_0
    :try_start_3
    invoke-virtual {p0}, Ljava/io/BufferedReader;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 366
    if-eqz v2, :cond_1

    .line 367
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 361
    :cond_1
    return v1

    .line 359
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

    .line 366
    :cond_2
    if-eqz v2, :cond_3

    .line 367
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    goto :goto_3

    .line 364
    :catchall_2
    move-exception p0

    move-object v1, v2

    goto :goto_2

    :catchall_3
    move-exception p0

    .line 366
    :goto_2
    if-eqz v1, :cond_3

    .line 367
    invoke-virtual {v1}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 370
    :cond_3
    :goto_3
    return v0
.end method

.method private static isProcessAlive(Ljava/lang/Process;)Z
    .locals 1

    .line 318
    const/4 v0, 0x0

    if-nez p0, :cond_0

    .line 319
    return v0

    .line 322
    :cond_0
    :try_start_0
    invoke-virtual {p0}, Ljava/lang/Process;->exitValue()I
    :try_end_0
    .catch Ljava/lang/IllegalThreadStateException; {:try_start_0 .. :try_end_0} :catch_0

    .line 323
    return v0

    .line 324
    :catch_0
    move-exception p0

    .line 325
    const/4 p0, 0x1

    return p0
.end method

.method public static mirrorSaves(Landroid/content/Context;)V
    .locals 3

    .line 458
    :try_start_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v0

    .line 459
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object p0

    .line 460
    new-instance v1, Ljava/io/File;

    const-string v2, "normal_profile.json"

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 461
    invoke-static {v0, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 465
    :cond_0
    goto :goto_0

    .line 463
    :catchall_0
    move-exception p0

    .line 464
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

    .line 466
    :goto_0
    return-void
.end method

.method public static onActivityDestroy(Landroid/content/Context;)V
    .locals 4

    .line 254
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 255
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 256
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    .line 257
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 258
    new-instance v2, Ljava/lang/Thread;

    new-instance v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;

    invoke-direct {v3, p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;-><init>(Landroid/content/Context;J)V

    const-string p0, "InuBackendShutdownGrace"

    invoke-direct {v2, v3, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 270
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V

    .line 271
    return-void
.end method

.method public static onActivityPause(Landroid/content/Context;)V
    .locals 2

    .line 244
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 245
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;-><init>(Landroid/content/Context;)V

    const-string p0, "InuSaveMirrorPause"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 250
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 251
    return-void
.end method

.method public static onActivityResume(Landroid/content/Context;)V
    .locals 2

    .line 232
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 233
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 234
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 235
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;-><init>(Landroid/content/Context;)V

    const-string p0, "InuBackendResumeCheck"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 240
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 241
    return-void
.end method

.method public static onAppCreate(Landroid/content/Context;)V
    .locals 3

    .line 40
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 41
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 42
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;-><init>(Landroid/content/Context;)V

    const-string v2, "InuBackendPrewarm"

    invoke-direct {v0, v1, v2}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 47
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 49
    :try_start_0
    new-instance v0, Landroid/content/Intent;

    const-class v1, Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-direct {v0, p0, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 52
    goto :goto_0

    .line 50
    :catchall_0
    move-exception p0

    .line 51
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

    .line 53
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

    .line 547
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 548
    :try_start_0
    new-instance p1, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p1}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 549
    const/16 v0, 0x1000

    new-array v0, v0, [B

    .line 551
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 552
    const/4 v2, 0x0

    invoke-virtual {p1, v0, v2, v1}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 554
    :cond_0
    new-instance v0, Ljava/lang/String;

    invoke-virtual {p1}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p1

    sget-object v1, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v0, p1, v1}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 555
    if-eqz p0, :cond_1

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 554
    :cond_1
    return-object v0

    .line 547
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

.method private static readFileTail(Ljava/io/File;I)Ljava/lang/String;
    .locals 6

    .line 393
    const-string v0, ""

    if-eqz p0, :cond_4

    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_4

    if-gtz p1, :cond_0

    goto :goto_3

    .line 396
    :cond_0
    :try_start_0
    new-instance v1, Ljava/io/RandomAccessFile;

    const-string v2, "r"

    invoke-direct {v1, p0, v2}, Ljava/io/RandomAccessFile;-><init>(Ljava/io/File;Ljava/lang/String;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 397
    :try_start_1
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->length()J

    move-result-wide v2
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    .line 398
    const-wide/16 v4, 0x0

    cmp-long p0, v2, v4

    if-gtz p0, :cond_1

    .line 399
    nop

    .line 414
    :try_start_2
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    .line 399
    return-object v0

    .line 401
    :cond_1
    int-to-long p0, p1

    sub-long p0, v2, p0

    :try_start_3
    invoke-static {v4, v5, p0, p1}, Ljava/lang/Math;->max(JJ)J

    move-result-wide p0

    .line 402
    sub-long/2addr v2, p0

    long-to-int v3, v2

    .line 403
    invoke-virtual {v1, p0, p1}, Ljava/io/RandomAccessFile;->seek(J)V

    .line 404
    new-array p0, v3, [B

    .line 405
    const/4 p1, 0x0

    const/4 v2, 0x0

    .line 406
    :goto_0
    if-ge v2, v3, :cond_3

    .line 407
    sub-int v4, v3, v2

    invoke-virtual {v1, p0, v2, v4}, Ljava/io/RandomAccessFile;->read([BII)I

    move-result v4

    .line 408
    if-gez v4, :cond_2

    .line 409
    goto :goto_1

    .line 411
    :cond_2
    add-int/2addr v2, v4

    .line 412
    goto :goto_0

    .line 413
    :cond_3
    :goto_1
    new-instance v3, Ljava/lang/String;

    sget-object v4, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v3, p0, p1, v2, v4}, Ljava/lang/String;-><init>([BIILjava/nio/charset/Charset;)V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_0

    .line 414
    :try_start_4
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->close()V
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_2

    .line 413
    return-object v3

    .line 396
    :catchall_0
    move-exception p0

    :try_start_5
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->close()V
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_1

    goto :goto_2

    :catchall_1
    move-exception p1

    :try_start_6
    invoke-virtual {p0, p1}, Ljava/lang/Throwable;->addSuppressed(Ljava/lang/Throwable;)V

    :goto_2
    throw p0
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_2

    .line 414
    :catchall_2
    move-exception p0

    .line 415
    return-object v0

    .line 394
    :cond_4
    :goto_3
    return-object v0
.end method

.method private static readFileText(Ljava/io/File;)Ljava/lang/String;
    .locals 4
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 587
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 588
    :try_start_0
    new-instance p0, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p0}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 589
    const/16 v1, 0x1000

    new-array v1, v1, [B

    .line 591
    :goto_0
    invoke-virtual {v0, v1}, Ljava/io/FileInputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_0

    .line 592
    const/4 v3, 0x0

    invoke-virtual {p0, v1, v3, v2}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 594
    :cond_0
    new-instance v1, Ljava/lang/String;

    invoke-virtual {p0}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p0

    sget-object v2, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, p0, v2}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 595
    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 594
    return-object v1

    .line 587
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

    .line 445
    const-string v0, "InuStandalone"

    const-string v1, "normal_profile.json"

    :try_start_0
    new-instance v2, Ljava/io/File;

    invoke-direct {v2, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 446
    new-instance v3, Ljava/io/File;

    invoke-direct {v3, p1, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 447
    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    invoke-virtual {v3}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 448
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

    .line 449
    invoke-static {p1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 453
    :cond_0
    goto :goto_0

    .line 451
    :catchall_0
    move-exception p0

    .line 452
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

    .line 454
    :goto_0
    return-void
.end method

.method public static stopBackend(Landroid/content/Context;)V
    .locals 1

    .line 289
    if-eqz p0, :cond_0

    .line 290
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 292
    :cond_0
    sget-object p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter p0

    .line 293
    :try_start_0
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 294
    monitor-exit p0

    .line 295
    return-void

    .line 294
    :catchall_0
    move-exception v0

    monitor-exit p0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    throw v0
.end method

.method private static stopProcessLocked()V
    .locals 4

    .line 298
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    if-eqz v0, :cond_3

    .line 300
    const/4 v0, 0x0

    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroy()V

    .line 301
    const/4 v1, 0x0

    :goto_0
    const/16 v2, 0xa

    if-ge v1, v2, :cond_1

    .line 302
    sget-object v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v2

    if-nez v2, :cond_0

    .line 303
    goto :goto_1

    .line 305
    :cond_0
    const-wide/16 v2, 0x1e

    invoke-static {v2, v3}, Ljava/lang/Thread;->sleep(J)V

    .line 301
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 307
    :cond_1
    :goto_1
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    if-eqz v1, :cond_2

    .line 308
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroyForcibly()Ljava/lang/Process;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    goto :goto_2

    .line 310
    :catchall_0
    move-exception v1

    .line 312
    :cond_2
    :goto_2
    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 313
    nop

    .line 315
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

    .line 502
    invoke-virtual {p0}, Landroid/content/Context;->getAssets()Landroid/content/res/AssetManager;

    move-result-object p0

    .line 503
    const-string v0, "inubackend/version.txt"

    invoke-static {p0, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readAssetText(Landroid/content/res/AssetManager;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v0

    .line 504
    new-instance v1, Ljava/io/File;

    const-string v2, "version.txt"

    invoke-direct {v1, p1, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 505
    new-instance p1, Ljava/io/File;

    const-string v2, "emulator.py"

    invoke-direct {p1, p3, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 506
    new-instance v2, Ljava/io/File;

    const-string v3, "stdlib.zip"

    invoke-direct {v2, p2, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 507
    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v3

    if-eqz v3, :cond_0

    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    .line 508
    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readFileText(Ljava/io/File;)Ljava/lang/String;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 509
    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result p1

    if-eqz p1, :cond_0

    .line 510
    return-void

    .line 513
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

    .line 514
    invoke-virtual {p2}, Ljava/io/File;->mkdirs()Z

    .line 515
    invoke-virtual {p3}, Ljava/io/File;->mkdirs()Z

    .line 517
    const-string p1, "inubackend/stdlib.zip"

    invoke-static {p0, p1, v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyAssetToFile(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/io/File;)V

    .line 518
    const-string p1, "inubackend/server_bundle.zip"

    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 519
    :try_start_0
    new-instance p1, Ljava/util/zip/ZipInputStream;

    invoke-direct {p1, p0}, Ljava/util/zip/ZipInputStream;-><init>(Ljava/io/InputStream;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_4

    .line 521
    const p2, 0x8000

    :try_start_1
    new-array p2, p2, [B

    .line 522
    :goto_0
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->getNextEntry()Ljava/util/zip/ZipEntry;

    move-result-object v2

    if-eqz v2, :cond_4

    .line 523
    new-instance v3, Ljava/io/File;

    invoke-virtual {v2}, Ljava/util/zip/ZipEntry;->getName()Ljava/lang/String;

    move-result-object v4

    invoke-direct {v3, p3, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 524
    invoke-virtual {v2}, Ljava/util/zip/ZipEntry;->isDirectory()Z

    move-result v2

    if-eqz v2, :cond_1

    .line 525
    invoke-virtual {v3}, Ljava/io/File;->mkdirs()Z

    goto :goto_2

    .line 527
    :cond_1
    invoke-virtual {v3}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v2

    .line 528
    if-eqz v2, :cond_2

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v4

    if-nez v4, :cond_2

    .line 529
    invoke-virtual {v2}, Ljava/io/File;->mkdirs()Z

    .line 531
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

    .line 532
    new-instance v4, Ljava/io/FileOutputStream;

    invoke-direct {v4, v2}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 534
    :goto_1
    :try_start_2
    invoke-virtual {p1, p2}, Ljava/util/zip/ZipInputStream;->read([B)I

    move-result v5

    if-lez v5, :cond_3

    .line 535
    const/4 v6, 0x0

    invoke-virtual {v4, p2, v6, v5}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_0

    goto :goto_1

    .line 537
    :cond_3
    :try_start_3
    invoke-virtual {v4}, Ljava/io/FileOutputStream;->close()V

    .line 538
    invoke-virtual {v2, v3}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 540
    :goto_2
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->closeEntry()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 541
    goto :goto_0

    .line 532
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

    .line 542
    :cond_4
    :try_start_6
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->close()V
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_4

    if-eqz p0, :cond_5

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 543
    :cond_5
    invoke-static {v1, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->writeFileText(Ljava/io/File;Ljava/lang/String;)V

    .line 544
    return-void

    .line 518
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

    .line 274
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 275
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    if-eqz v0, :cond_0

    .line 277
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v0

    .line 278
    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    .line 279
    monitor-exit v0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 280
    if-nez v1, :cond_0

    const/16 v0, 0x12c

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0

    if-nez v0, :cond_0

    .line 281
    const-string v0, "InuStandalone"

    const-string v1, "Watchdog detected stopped backend while game active; restarting"

    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 282
    const-wide/16 v0, 0x3a98

    invoke-static {p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;J)V

    goto :goto_0

    .line 279
    :catchall_0
    move-exception p0

    :try_start_1
    monitor-exit v0
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    throw p0

    .line 285
    :cond_0
    :goto_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 286
    return-void
.end method

.method private static writeFileText(Ljava/io/File;Ljava/lang/String;)V
    .locals 2
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 599
    invoke-virtual {p0}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 600
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 601
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 603
    :cond_0
    new-instance v0, Ljava/io/FileOutputStream;

    invoke-direct {v0, p0}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V

    .line 604
    :try_start_0
    sget-object p0, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-virtual {p1, p0}, Ljava/lang/String;->getBytes(Ljava/nio/charset/Charset;)[B

    move-result-object p0

    invoke-virtual {v0, p0}, Ljava/io/FileOutputStream;->write([B)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 605
    invoke-virtual {v0}, Ljava/io/FileOutputStream;->close()V

    .line 606
    return-void

    .line 603
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
