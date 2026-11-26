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

    .line 31
    new-instance v0, Ljava/lang/Object;

    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    .line 32
    const/4 v0, 0x0

    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 33
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 34
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 35
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 36
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    return-void
.end method

.method private constructor <init>()V
    .locals 0

    .line 38
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method static synthetic access$000()Z
    .locals 1

    .line 25
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    return v0
.end method

.method static synthetic access$102(J)J
    .locals 0

    .line 25
    sput-wide p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    return-wide p0
.end method

.method static synthetic access$200()J
    .locals 2

    .line 25
    sget-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    return-wide v0
.end method

.method static synthetic access$300(I)Z
    .locals 0

    .line 25
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

    .line 627
    invoke-virtual {p2}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 628
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 629
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 631
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

    .line 632
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 633
    :try_start_0
    new-instance p1, Ljava/io/FileOutputStream;

    invoke-direct {p1, v1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 634
    const v0, 0x8000

    :try_start_1
    new-array v0, v0, [B

    .line 636
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_1

    .line 637
    const/4 v3, 0x0

    invoke-virtual {p1, v0, v3, v2}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 639
    :cond_1
    :try_start_2
    invoke-virtual {p1}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    if-eqz p0, :cond_2

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 640
    :cond_2
    invoke-virtual {v1, p2}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 641
    return-void

    .line 632
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

    .line 534
    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_0

    .line 535
    return-void

    .line 537
    :cond_0
    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_1

    .line 538
    invoke-virtual {p1}, Ljava/io/File;->mkdirs()Z

    .line 540
    :cond_1
    invoke-virtual {p0}, Ljava/io/File;->listFiles()[Ljava/io/File;

    move-result-object p0

    .line 541
    if-nez p0, :cond_2

    .line 542
    return-void

    .line 544
    :cond_2
    array-length v0, p0

    const/4 v1, 0x0

    :goto_0
    if-ge v1, v0, :cond_8

    aget-object v2, p0, v1

    .line 545
    invoke-virtual {v2}, Ljava/io/File;->getName()Ljava/lang/String;

    move-result-object v3

    .line 546
    invoke-virtual {v2}, Ljava/io/File;->isDirectory()Z

    move-result v4

    if-eqz v4, :cond_3

    .line 547
    const-string v4, "backups"

    invoke-virtual {v4, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v4

    if-eqz v4, :cond_7

    .line 548
    new-instance v4, Ljava/io/File;

    invoke-direct {v4, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-static {v2, v4}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V

    goto :goto_1

    .line 552
    :cond_3
    const-string v4, "."

    invoke-virtual {v3, v4}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_4

    .line 553
    goto :goto_1

    .line 555
    :cond_4
    const-string v5, ".json"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-nez v5, :cond_5

    const-string v5, ".jsonl"

    invoke-virtual {v3, v5}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :cond_7

    .line 556
    :cond_5
    new-instance v5, Ljava/io/File;

    invoke-direct {v5, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 557
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

    .line 558
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

    .line 559
    invoke-static {v2, v6}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyFile(Ljava/io/File;Ljava/io/File;)V

    .line 560
    invoke-virtual {v6, v5}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 544
    :cond_7
    :goto_1
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 564
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

    .line 644
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 645
    :try_start_0
    new-instance p0, Ljava/io/FileOutputStream;

    invoke-direct {p0, p1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 646
    const p1, 0x8000

    :try_start_1
    new-array p1, p1, [B

    .line 648
    :goto_0
    invoke-virtual {v0, p1}, Ljava/io/FileInputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 649
    const/4 v2, 0x0

    invoke-virtual {p0, p1, v2, v1}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    goto :goto_0

    .line 651
    :cond_0
    :try_start_2
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 652
    return-void

    .line 644
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

.method private static deleteRecursive(Ljava/io/File;)V
    .locals 4

    .line 486
    if-eqz p0, :cond_2

    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v0

    if-nez v0, :cond_0

    goto :goto_1

    .line 489
    :cond_0
    invoke-virtual {p0}, Ljava/io/File;->isDirectory()Z

    move-result v0

    if-eqz v0, :cond_1

    .line 490
    invoke-virtual {p0}, Ljava/io/File;->listFiles()[Ljava/io/File;

    move-result-object v0

    .line 491
    if-eqz v0, :cond_1

    .line 492
    array-length v1, v0

    const/4 v2, 0x0

    :goto_0
    if-ge v2, v1, :cond_1

    aget-object v3, v0, v2

    .line 493
    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->deleteRecursive(Ljava/io/File;)V

    .line 492
    add-int/lit8 v2, v2, 0x1

    goto :goto_0

    .line 497
    :cond_1
    invoke-virtual {p0}, Ljava/io/File;->delete()Z

    .line 498
    return-void

    .line 487
    :cond_2
    :goto_1
    return-void
.end method

.method public static ensureStarted(Landroid/content/Context;)V
    .locals 10

    .line 57
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 58
    invoke-static {}, Landroid/os/Looper;->myLooper()Landroid/os/Looper;

    move-result-object v0

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    if-ne v0, v1, :cond_4

    .line 59
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 60
    const-wide/16 v1, 0x0

    sput-wide v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 61
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

    .line 62
    return-void

    .line 64
    :cond_0
    new-instance v3, Ljava/lang/Thread;

    new-instance v4, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;

    invoke-direct {v4, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$2;-><init>(Landroid/content/Context;)V

    const-string p0, "InuBackendActivityStart"

    invoke-direct {v3, v4, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 70
    invoke-virtual {v3, v0}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 71
    invoke-virtual {v3}, Ljava/lang/Thread;->start()V

    .line 72
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v4

    .line 74
    :goto_0
    :try_start_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v6

    sub-long/2addr v6, v4

    const-wide/16 v8, 0xbb8

    cmp-long p0, v6, v8

    if-gez p0, :cond_3

    .line 75
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

    .line 76
    goto :goto_1

    .line 78
    :cond_1
    invoke-virtual {v3}, Ljava/lang/Thread;->isAlive()Z

    move-result p0

    if-nez p0, :cond_2

    .line 79
    goto :goto_1

    .line 81
    :cond_2
    const-wide/16 v6, 0x28

    invoke-static {v6, v7}, Ljava/lang/Thread;->sleep(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_0

    .line 85
    :cond_3
    :goto_1
    goto :goto_2

    .line 83
    :catch_0
    move-exception p0

    .line 84
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/Thread;->interrupt()V

    .line 86
    :goto_2
    return-void

    .line 88
    :cond_4
    const-wide/16 v0, 0x2ee0

    invoke-static {p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;J)V

    .line 89
    return-void
.end method

.method public static ensureStarted(Landroid/content/Context;J)V
    .locals 20

    .line 92
    invoke-virtual/range {p0 .. p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object v1

    .line 93
    const/4 v2, 0x1

    sput-boolean v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 94
    const-wide/16 v3, 0x0

    sput-wide v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 95
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v5

    .line 102
    sget-object v7, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v7

    .line 103
    :try_start_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v8

    .line 104
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0

    if-eqz v0, :cond_1

    sget-wide v10, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    sub-long v10, v8, v10

    const-wide/16 v12, 0x9c4

    cmp-long v0, v10, v12

    if-ltz v0, :cond_0

    const/16 v0, 0x15e

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0

    if-eqz v0, :cond_1

    .line 105
    :cond_0
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 106
    monitor-exit v7

    return-void

    .line 108
    :cond_1
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0

    if-nez v0, :cond_2

    const/16 v0, 0xfa

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0

    if-eqz v0, :cond_2

    .line 109
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 110
    const-string v0, "InuStandalone"

    const-string v1, "Reusing existing healthy loopback backend on 127.0.0.1:18082"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 111
    monitor-exit v7

    return-void

    .line 113
    :cond_2
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0

    if-eqz v0, :cond_3

    sget-wide v11, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    cmp-long v0, v11, v3

    if-lez v0, :cond_3

    sget-wide v11, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    sub-long/2addr v8, v11

    const-wide/16 v11, 0x61a8

    cmp-long v0, v8, v11

    if-gez v0, :cond_3

    .line 114
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 115
    sget-wide v8, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 116
    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v11

    .line 117
    new-instance v12, Ljava/io/File;

    const-string v13, "backend_stdout.log"

    invoke-direct {v12, v11, v13}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 118
    invoke-virtual {v11}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v11

    .line 119
    invoke-virtual {v1}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;

    move-result-object v1

    iget-object v1, v1, Landroid/content/pm/ApplicationInfo;->nativeLibraryDir:Ljava/lang/String;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_5

    .line 120
    move-wide/from16 v16, v3

    move-wide v13, v8

    move-object v3, v12

    const/4 v9, 0x0

    move-object v12, v1

    const/4 v1, 0x1

    move-object v2, v0

    goto/16 :goto_3

    .line 121
    :cond_3
    nop

    .line 122
    nop

    .line 123
    nop

    .line 124
    nop

    .line 126
    :try_start_1
    new-instance v0, Ljava/io/File;

    invoke-virtual {v1}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object v8

    const-string v9, "inubackend"

    invoke-direct {v0, v8, v9}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 127
    new-instance v8, Ljava/io/File;

    const-string v9, "py"

    invoke-direct {v8, v0, v9}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 128
    new-instance v9, Ljava/io/File;

    const-string v11, "server"

    invoke-direct {v9, v0, v11}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 129
    invoke-static {v1, v0, v8, v9}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->unpackAssetsIfNeeded(Landroid/content/Context;Ljava/io/File;Ljava/io/File;Ljava/io/File;)V

    .line 131
    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v0

    .line 132
    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v11

    .line 133
    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v12

    .line 134
    invoke-static {v0, v12}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->restoreFromMirrorIfEmpty(Ljava/io/File;Ljava/io/File;)V

    .line 136
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 138
    invoke-virtual {v1}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;

    move-result-object v12

    iget-object v12, v12, Landroid/content/pm/ApplicationInfo;->nativeLibraryDir:Ljava/lang/String;

    .line 139
    new-instance v13, Ljava/io/File;

    const-string v14, "libinubackend.so"

    invoke-direct {v13, v12, v14}, Ljava/io/File;-><init>(Ljava/lang/String;Ljava/lang/String;)V

    .line 140
    new-instance v14, Ljava/io/File;

    const-string v15, "emulator.py"

    invoke-direct {v14, v9, v15}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 141
    new-instance v15, Ljava/io/File;

    move-wide/from16 v16, v3

    const-string v3, "rpc_trace.log"

    invoke-direct {v15, v0, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 142
    new-instance v3, Ljava/io/File;

    const-string v4, "backend_stdout.log"

    invoke-direct {v3, v0, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 143
    new-instance v0, Ljava/io/File;

    const-string v4, "lib-dynload"

    invoke-direct {v0, v8, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 144
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 146
    new-instance v4, Ljava/lang/ProcessBuilder;

    const/16 p0, 0x0

    const/16 v10, 0xc

    new-array v10, v10, [Ljava/lang/String;

    .line 147
    invoke-virtual {v13}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v13

    aput-object v13, v10, p0

    .line 148
    invoke-virtual {v14}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v13

    aput-object v13, v10, v2

    const-string v13, "--env"

    const/4 v14, 0x2

    aput-object v13, v10, v14

    const-string v13, "dev"

    const/4 v14, 0x3

    aput-object v13, v10, v14

    const-string v13, "--host"

    const/4 v14, 0x4

    aput-object v13, v10, v14

    const-string v13, "127.0.0.1"

    const/4 v14, 0x5

    aput-object v13, v10, v14

    const-string v13, "--port"

    const/4 v14, 0x6

    aput-object v13, v10, v14

    .line 151
    const/16 v13, 0x46a2

    invoke-static {v13}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v13

    const/4 v14, 0x7

    aput-object v13, v10, v14

    const-string v13, "--data-dir"

    const/16 v14, 0x8

    aput-object v13, v10, v14

    const/16 v13, 0x9

    aput-object v11, v10, v13

    const-string v13, "--trace-path"

    const/16 v14, 0xa

    aput-object v13, v10, v14

    .line 153
    invoke-virtual {v15}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v13

    const/16 v14, 0xb

    aput-object v13, v10, v14

    invoke-direct {v4, v10}, Ljava/lang/ProcessBuilder;-><init>([Ljava/lang/String;)V

    .line 155
    invoke-virtual {v4, v9}, Ljava/lang/ProcessBuilder;->directory(Ljava/io/File;)Ljava/lang/ProcessBuilder;

    .line 156
    invoke-virtual {v4, v2}, Ljava/lang/ProcessBuilder;->redirectErrorStream(Z)Ljava/lang/ProcessBuilder;

    .line 157
    invoke-static {v3}, Ljava/lang/ProcessBuilder$Redirect;->appendTo(Ljava/io/File;)Ljava/lang/ProcessBuilder$Redirect;

    move-result-object v10

    invoke-virtual {v4, v10}, Ljava/lang/ProcessBuilder;->redirectOutput(Ljava/lang/ProcessBuilder$Redirect;)Ljava/lang/ProcessBuilder;

    .line 159
    invoke-virtual {v4}, Ljava/lang/ProcessBuilder;->environment()Ljava/util/Map;

    move-result-object v10

    .line 160
    const-string v13, "LD_LIBRARY_PATH"

    invoke-interface {v10, v13, v12}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 161
    const-string v13, "INUYASHA_NATIVE_LIB_DIR"

    invoke-interface {v10, v13, v12}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 162
    const-string v13, "INUYASHA_DYNLOAD_DIR"

    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v14

    invoke-interface {v10, v13, v14}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 163
    const-string v13, "PYTHONHOME"

    invoke-virtual {v8}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v14

    invoke-interface {v10, v13, v14}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 164
    const-string v13, "PYTHONPATH"

    new-instance v14, Ljava/lang/StringBuilder;

    invoke-direct {v14}, Ljava/lang/StringBuilder;-><init>()V

    new-instance v15, Ljava/io/File;

    const-string v2, "stdlib.zip"

    invoke-direct {v15, v8, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 166
    invoke-virtual {v15}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v14, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    const-string v8, ":"

    invoke-virtual {v2, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v2

    .line 167
    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v2, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    const-string v2, ":"

    invoke-virtual {v0, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    .line 168
    invoke-virtual {v9}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v0, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    .line 164
    invoke-interface {v10, v13, v0}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 170
    const-string v0, "PYTHONNOUSERSITE"

    const-string v2, "1"

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 171
    const-string v0, "PYTHONDONTWRITEBYTECODE"

    const-string v2, "1"

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 172
    const-string v0, "INUYASHA_SEED_DIR"

    new-instance v2, Ljava/io/File;

    const-string v8, "seeds"

    invoke-direct {v2, v9, v8}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v2}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 173
    const-string v0, "INUYASHA_PUBLIC_BACKUP_PATH"

    const-string v2, "/sdcard/Download/InuYasha_Save_Backup.json"

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 174
    const-string v0, "INUYASHA_SERVER_DIR"

    invoke-virtual {v9}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 175
    const-string v0, "INUYASHA_CLIENT_OTA_DIR"

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getClientOtaDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v2

    invoke-virtual {v2}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 176
    nop

    .line 177
    const-string v2, ""
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_4

    .line 179
    :try_start_2
    invoke-virtual {v1}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;

    move-result-object v0

    invoke-virtual {v1}, Landroid/content/Context;->getPackageName()Ljava/lang/String;

    move-result-object v8
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    const/4 v9, 0x0

    :try_start_3
    invoke-virtual {v0, v8, v9}, Landroid/content/pm/PackageManager;->getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;

    move-result-object v0

    .line 180
    if-eqz v0, :cond_5

    .line 181
    iget v8, v0, Landroid/content/pm/PackageInfo;->versionCode:I
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_1

    .line 182
    :try_start_4
    iget-object v13, v0, Landroid/content/pm/PackageInfo;->versionName:Ljava/lang/String;

    if-eqz v13, :cond_4

    iget-object v0, v0, Landroid/content/pm/PackageInfo;->versionName:Ljava/lang/String;

    goto :goto_0

    :cond_4
    const-string v0, ""
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_0

    :goto_0
    move-object v2, v0

    goto :goto_2

    .line 184
    :catchall_0
    move-exception v0

    goto :goto_2

    .line 180
    :cond_5
    const/4 v8, 0x0

    goto :goto_2

    .line 184
    :catchall_1
    move-exception v0

    goto :goto_1

    :catchall_2
    move-exception v0

    const/4 v9, 0x0

    :goto_1
    const/4 v8, 0x0

    :goto_2
    nop

    .line 185
    :try_start_5
    const-string v0, "INUYASHA_APK_VERSION_CODE"

    invoke-static {v8}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v8

    invoke-interface {v10, v0, v8}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 186
    const-string v0, "INUYASHA_APK_VERSION_NAME"

    invoke-interface {v10, v0, v2}, Ljava/util/Map;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    .line 188
    invoke-virtual {v4}, Ljava/lang/ProcessBuilder;->start()Ljava/lang/Process;

    move-result-object v0

    .line 189
    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 190
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v13

    sput-wide v13, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 191
    sput-wide v16, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 193
    nop

    .line 194
    new-instance v2, Ljava/lang/Thread;

    new-instance v4, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;

    invoke-direct {v4, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;-><init>(Ljava/lang/Process;Landroid/content/Context;)V

    const-string v1, "InuBackendExitWatch"

    invoke-direct {v2, v4, v1}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 211
    const/4 v1, 0x1

    invoke-virtual {v2, v1}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 212
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V
    :try_end_5
    .catchall {:try_start_5 .. :try_end_5} :catchall_4

    .line 216
    nop

    .line 217
    nop

    .line 218
    :try_start_6
    sget-wide v13, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastLaunchStartMs:J

    .line 219
    nop

    .line 220
    nop

    .line 221
    move-object v2, v0

    .line 223
    :goto_3
    monitor-exit v7
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_5

    .line 225
    nop

    .line 226
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v7

    .line 228
    :goto_4
    :try_start_7
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v18

    sub-long v18, v18, v7

    cmp-long v0, v18, p1

    if-gez v0, :cond_a

    .line 229
    sget-wide v18, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J

    .line 230
    cmp-long v0, v18, v16

    if-lez v0, :cond_6

    cmp-long v0, v18, v13

    if-ltz v0, :cond_6

    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0

    if-eqz v0, :cond_6

    .line 231
    nop

    .line 232
    goto :goto_7

    .line 234
    :cond_6
    const/16 v0, 0x12c

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0
    :try_end_7
    .catch Ljava/lang/InterruptedException; {:try_start_7 .. :try_end_7} :catch_1

    if-eqz v0, :cond_7

    .line 235
    nop

    .line 236
    :try_start_8
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v3

    sput-wide v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastHealthOkMs:J
    :try_end_8
    .catch Ljava/lang/InterruptedException; {:try_start_8 .. :try_end_8} :catch_0

    .line 237
    goto :goto_7

    .line 252
    :catch_0
    move-exception v0

    const/4 v9, 0x1

    goto :goto_8

    .line 239
    :cond_7
    :try_start_9
    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v0
    :try_end_9
    .catch Ljava/lang/InterruptedException; {:try_start_9 .. :try_end_9} :catch_1

    if-nez v0, :cond_9

    .line 240
    nop

    .line 242
    const/4 v1, -0x1

    if-eqz v2, :cond_8

    .line 243
    :try_start_a
    invoke-virtual {v2}, Ljava/lang/Process;->exitValue()I

    move-result v1
    :try_end_a
    .catchall {:try_start_a .. :try_end_a} :catchall_3

    goto :goto_5

    .line 245
    :catchall_3
    move-exception v0

    :cond_8
    :goto_5
    nop

    .line 246
    const/16 v0, 0x320

    :try_start_b
    invoke-static {v3, v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readFileTail(Ljava/io/File;I)Ljava/lang/String;

    move-result-object v0

    .line 247
    const-string v3, "InuStandalone"

    new-instance v4, Ljava/lang/StringBuilder;

    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V

    const-string v7, "BACKEND_EXITED_EARLY exit="

    invoke-virtual {v4, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v4

    invoke-virtual {v4, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v4, " tail="

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v3, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    .line 248
    goto :goto_6

    .line 250
    :cond_9
    const-wide/16 v18, 0x3c

    invoke-static/range {v18 .. v19}, Ljava/lang/Thread;->sleep(J)V
    :try_end_b
    .catch Ljava/lang/InterruptedException; {:try_start_b .. :try_end_b} :catch_1

    .line 251
    goto :goto_4

    .line 254
    :cond_a
    :goto_6
    const/4 v1, 0x0

    :goto_7
    goto :goto_9

    .line 252
    :catch_1
    move-exception v0

    .line 253
    :goto_8
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Thread;->interrupt()V

    move v1, v9

    .line 255
    :goto_9
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v3

    sub-long/2addr v3, v5

    .line 256
    const-string v0, "InuStandalone"

    new-instance v5, Ljava/lang/StringBuilder;

    invoke-direct {v5}, Ljava/lang/StringBuilder;-><init>()V

    const-string v6, "BACKEND_START ready="

    invoke-virtual {v5, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v5

    invoke-virtual {v5, v1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v5, " alive="

    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    .line 259
    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v2

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, " elapsed_ms="

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v3, v4}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, " save_dir="

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v11}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, " native_lib="

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v12}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    .line 256
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 264
    return-void

    .line 213
    :catchall_4
    move-exception v0

    .line 214
    :try_start_c
    const-string v1, "InuStandalone"

    const-string v2, "Failed to start embedded backend"

    invoke-static {v1, v2, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    .line 215
    monitor-exit v7

    return-void

    .line 223
    :catchall_5
    move-exception v0

    monitor-exit v7
    :try_end_c
    .catchall {:try_start_c .. :try_end_c} :catchall_5

    throw v0
.end method

.method public static getClientOtaDir(Landroid/content/Context;)Ljava/io/File;
    .locals 5

    .line 471
    const/4 v0, 0x0

    invoke-virtual {p0, v0}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    .line 472
    const-string v1, "Download"

    const-string v2, "moqikaka"

    if-eqz v0, :cond_0

    .line 473
    new-instance v3, Ljava/io/File;

    new-instance v4, Ljava/io/File;

    invoke-direct {v4, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-direct {v3, v4, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 474
    invoke-static {v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isDirWritable(Ljava/io/File;)Z

    move-result v0

    if-eqz v0, :cond_0

    .line 475
    return-object v3

    .line 478
    :cond_0
    new-instance v0, Ljava/io/File;

    new-instance v3, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    invoke-direct {v3, p0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-direct {v0, v3, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 479
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_1

    .line 480
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 482
    :cond_1
    return-object v0
.end method

.method public static getMirrorDir(Landroid/content/Context;)Ljava/io/File;
    .locals 2

    .line 501
    new-instance v0, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    const-string v1, "saves_mirror"

    invoke-direct {v0, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 502
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_0

    .line 503
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 505
    :cond_0
    return-object v0
.end method

.method public static getSaveDir(Landroid/content/Context;)Ljava/io/File;
    .locals 4

    .line 455
    const/4 v0, 0x0

    invoke-virtual {p0, v0}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    .line 456
    const-string v1, "saves"

    if-eqz v0, :cond_1

    .line 457
    new-instance v2, Ljava/io/File;

    invoke-direct {v2, v0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 458
    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isDirWritable(Ljava/io/File;)Z

    move-result v0

    if-eqz v0, :cond_0

    .line 459
    return-object v2

    .line 461
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

    .line 463
    :cond_1
    new-instance v0, Ljava/io/File;

    invoke-virtual {p0}, Landroid/content/Context;->getFilesDir()Ljava/io/File;

    move-result-object p0

    invoke-direct {v0, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 464
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result p0

    if-nez p0, :cond_2

    .line 465
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 467
    :cond_2
    return-object v0
.end method

.method private static isDirWritable(Ljava/io/File;)Z
    .locals 5

    .line 410
    const/4 v0, 0x0

    :try_start_0
    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    invoke-virtual {p0}, Ljava/io/File;->mkdirs()Z

    move-result v1

    if-nez v1, :cond_0

    .line 411
    return v0

    .line 413
    :cond_0
    invoke-virtual {p0}, Ljava/io/File;->isDirectory()Z

    move-result v1

    if-nez v1, :cond_1

    .line 414
    return v0

    .line 416
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

    .line 417
    new-instance p0, Ljava/io/FileOutputStream;

    invoke-direct {p0, v1}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 418
    const/16 v2, 0x20

    :try_start_1
    invoke-virtual {p0, v2}, Ljava/io/FileOutputStream;->write(I)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    .line 419
    :try_start_2
    invoke-virtual {p0}, Ljava/io/FileOutputStream;->close()V

    .line 420
    invoke-virtual {v1}, Ljava/io/File;->delete()Z
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    .line 421
    const/4 p0, 0x1

    return p0

    .line 417
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

    .line 422
    :catchall_2
    move-exception p0

    .line 423
    return v0
.end method

.method public static isLoopbackHealthy(I)Z
    .locals 7

    .line 365
    invoke-static {}, Landroid/os/Looper;->myLooper()Landroid/os/Looper;

    move-result-object v0

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    if-ne v0, v1, :cond_0

    .line 366
    const/4 v0, 0x1

    new-array v1, v0, [Z

    .line 367
    new-instance v2, Ljava/lang/Thread;

    new-instance v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;

    invoke-direct {v3, v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;-><init>([ZI)V

    const-string v4, "InuHealthProbe"

    invoke-direct {v2, v3, v4}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 373
    invoke-virtual {v2, v0}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 374
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V

    .line 376
    int-to-long v3, p0

    const-wide/16 v5, 0xfa

    add-long/2addr v3, v5

    :try_start_0
    invoke-virtual {v2, v3, v4}, Ljava/lang/Thread;->join(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0

    .line 379
    goto :goto_0

    .line 377
    :catch_0
    move-exception p0

    .line 378
    invoke-static {}, Ljava/lang/Thread;->currentThread()Ljava/lang/Thread;

    move-result-object p0

    invoke-virtual {p0}, Ljava/lang/Thread;->interrupt()V

    .line 380
    :goto_0
    const/4 p0, 0x0

    aget-boolean p0, v1, p0

    return p0

    .line 382
    :cond_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthyDirect(I)Z

    move-result p0

    return p0
.end method

.method private static isLoopbackHealthyDirect(I)Z
    .locals 5

    .line 386
    nop

    .line 388
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

    .line 389
    :try_start_1
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V

    .line 390
    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V

    .line 391
    const-string p0, "GET"

    invoke-virtual {v2, p0}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V

    .line 392
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getResponseCode()I

    move-result p0

    .line 393
    const/16 v1, 0xc8

    if-ne p0, v1, :cond_2

    .line 394
    new-instance p0, Ljava/io/BufferedReader;

    new-instance v1, Ljava/io/InputStreamReader;

    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;

    move-result-object v3

    sget-object v4, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, v3, v4}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/nio/charset/Charset;)V

    invoke-direct {p0, v1}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 395
    :try_start_2
    invoke-virtual {p0}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;

    move-result-object v1

    .line 396
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

    .line 397
    :goto_0
    :try_start_3
    invoke-virtual {p0}, Ljava/io/BufferedReader;->close()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 401
    if-eqz v2, :cond_1

    .line 402
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 396
    :cond_1
    return v1

    .line 394
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

    .line 401
    :cond_2
    if-eqz v2, :cond_3

    .line 402
    invoke-virtual {v2}, Ljava/net/HttpURLConnection;->disconnect()V

    goto :goto_3

    .line 399
    :catchall_2
    move-exception p0

    move-object v1, v2

    goto :goto_2

    :catchall_3
    move-exception p0

    .line 401
    :goto_2
    if-eqz v1, :cond_3

    .line 402
    invoke-virtual {v1}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 405
    :cond_3
    :goto_3
    return v0
.end method

.method private static isProcessAlive(Ljava/lang/Process;)Z
    .locals 1

    .line 353
    const/4 v0, 0x0

    if-nez p0, :cond_0

    .line 354
    return v0

    .line 357
    :cond_0
    :try_start_0
    invoke-virtual {p0}, Ljava/lang/Process;->exitValue()I
    :try_end_0
    .catch Ljava/lang/IllegalThreadStateException; {:try_start_0 .. :try_end_0} :catch_0

    .line 358
    return v0

    .line 359
    :catch_0
    move-exception p0

    .line 360
    const/4 p0, 0x1

    return p0
.end method

.method public static mirrorSaves(Landroid/content/Context;)V
    .locals 3

    .line 523
    :try_start_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getSaveDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object v0

    .line 524
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getMirrorDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object p0

    .line 525
    new-instance v1, Ljava/io/File;

    const-string v2, "normal_profile.json"

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 526
    invoke-static {v0, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 530
    :cond_0
    goto :goto_0

    .line 528
    :catchall_0
    move-exception p0

    .line 529
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

    .line 531
    :goto_0
    return-void
.end method

.method public static onActivityDestroy(Landroid/content/Context;)V
    .locals 4

    .line 289
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 290
    const/4 v0, 0x0

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 291
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    .line 292
    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 293
    new-instance v2, Ljava/lang/Thread;

    new-instance v3, Lcom/cmn/inuyasha/standalone/LocalBackendManager$6;

    invoke-direct {v3, p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$6;-><init>(Landroid/content/Context;J)V

    const-string p0, "InuBackendShutdownGrace"

    invoke-direct {v2, v3, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 305
    invoke-virtual {v2}, Ljava/lang/Thread;->start()V

    .line 306
    return-void
.end method

.method public static onActivityPause(Landroid/content/Context;)V
    .locals 2

    .line 279
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 280
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;-><init>(Landroid/content/Context;)V

    const-string p0, "InuSaveMirrorPause"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 285
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 286
    return-void
.end method

.method public static onActivityResume(Landroid/content/Context;)V
    .locals 2

    .line 267
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 268
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 269
    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->lastDestroyAtMs:J

    .line 270
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$4;-><init>(Landroid/content/Context;)V

    const-string p0, "InuBackendResumeCheck"

    invoke-direct {v0, v1, p0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 275
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 276
    return-void
.end method

.method public static onAppCreate(Landroid/content/Context;)V
    .locals 3

    .line 41
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 42
    const/4 v0, 0x1

    sput-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    .line 43
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;

    invoke-direct {v1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager$1;-><init>(Landroid/content/Context;)V

    const-string v2, "InuBackendPrewarm"

    invoke-direct {v0, v1, v2}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    .line 48
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 50
    :try_start_0
    new-instance v0, Landroid/content/Intent;

    const-class v1, Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-direct {v0, p0, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 53
    goto :goto_0

    .line 51
    :catchall_0
    move-exception p0

    .line 52
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

    .line 54
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

    .line 615
    invoke-virtual {p0, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 616
    :try_start_0
    new-instance p1, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p1}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 617
    const/16 v0, 0x1000

    new-array v0, v0, [B

    .line 619
    :goto_0
    invoke-virtual {p0, v0}, Ljava/io/InputStream;->read([B)I

    move-result v1

    if-lez v1, :cond_0

    .line 620
    const/4 v2, 0x0

    invoke-virtual {p1, v0, v2, v1}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 622
    :cond_0
    new-instance v0, Ljava/lang/String;

    invoke-virtual {p1}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p1

    sget-object v1, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v0, p1, v1}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 623
    if-eqz p0, :cond_1

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 622
    :cond_1
    return-object v0

    .line 615
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

    .line 428
    const-string v0, ""

    if-eqz p0, :cond_4

    invoke-virtual {p0}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_4

    if-gtz p1, :cond_0

    goto :goto_3

    .line 431
    :cond_0
    :try_start_0
    new-instance v1, Ljava/io/RandomAccessFile;

    const-string v2, "r"

    invoke-direct {v1, p0, v2}, Ljava/io/RandomAccessFile;-><init>(Ljava/io/File;Ljava/lang/String;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_2

    .line 432
    :try_start_1
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->length()J

    move-result-wide v2
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    .line 433
    const-wide/16 v4, 0x0

    cmp-long p0, v2, v4

    if-gtz p0, :cond_1

    .line 434
    nop

    .line 449
    :try_start_2
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->close()V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_2

    .line 434
    return-object v0

    .line 436
    :cond_1
    int-to-long p0, p1

    sub-long p0, v2, p0

    :try_start_3
    invoke-static {v4, v5, p0, p1}, Ljava/lang/Math;->max(JJ)J

    move-result-wide p0

    .line 437
    sub-long/2addr v2, p0

    long-to-int v3, v2

    .line 438
    invoke-virtual {v1, p0, p1}, Ljava/io/RandomAccessFile;->seek(J)V

    .line 439
    new-array p0, v3, [B

    .line 440
    const/4 p1, 0x0

    const/4 v2, 0x0

    .line 441
    :goto_0
    if-ge v2, v3, :cond_3

    .line 442
    sub-int v4, v3, v2

    invoke-virtual {v1, p0, v2, v4}, Ljava/io/RandomAccessFile;->read([BII)I

    move-result v4

    .line 443
    if-gez v4, :cond_2

    .line 444
    goto :goto_1

    .line 446
    :cond_2
    add-int/2addr v2, v4

    .line 447
    goto :goto_0

    .line 448
    :cond_3
    :goto_1
    new-instance v3, Ljava/lang/String;

    sget-object v4, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v3, p0, p1, v2, v4}, Ljava/lang/String;-><init>([BIILjava/nio/charset/Charset;)V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_0

    .line 449
    :try_start_4
    invoke-virtual {v1}, Ljava/io/RandomAccessFile;->close()V
    :try_end_4
    .catchall {:try_start_4 .. :try_end_4} :catchall_2

    .line 448
    return-object v3

    .line 431
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

    .line 449
    :catchall_2
    move-exception p0

    .line 450
    return-object v0

    .line 429
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

    .line 655
    new-instance v0, Ljava/io/FileInputStream;

    invoke-direct {v0, p0}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    .line 656
    :try_start_0
    new-instance p0, Ljava/io/ByteArrayOutputStream;

    invoke-direct {p0}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 657
    const/16 v1, 0x1000

    new-array v1, v1, [B

    .line 659
    :goto_0
    invoke-virtual {v0, v1}, Ljava/io/FileInputStream;->read([B)I

    move-result v2

    if-lez v2, :cond_0

    .line 660
    const/4 v3, 0x0

    invoke-virtual {p0, v1, v3, v2}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_0

    .line 662
    :cond_0
    new-instance v1, Ljava/lang/String;

    invoke-virtual {p0}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object p0

    sget-object v2, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-direct {v1, p0, v2}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 663
    invoke-virtual {v0}, Ljava/io/FileInputStream;->close()V

    .line 662
    return-object v1

    .line 655
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

    .line 510
    const-string v0, "InuStandalone"

    const-string v1, "normal_profile.json"

    :try_start_0
    new-instance v2, Ljava/io/File;

    invoke-direct {v2, p0, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 511
    new-instance v3, Ljava/io/File;

    invoke-direct {v3, p1, v1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 512
    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    invoke-virtual {v3}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_0

    .line 513
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

    .line 514
    invoke-static {p1, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyDirSaves(Ljava/io/File;Ljava/io/File;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 518
    :cond_0
    goto :goto_0

    .line 516
    :catchall_0
    move-exception p0

    .line 517
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

    .line 519
    :goto_0
    return-void
.end method

.method public static stopBackend(Landroid/content/Context;)V
    .locals 1

    .line 324
    if-eqz p0, :cond_0

    .line 325
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 327
    :cond_0
    sget-object p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter p0

    .line 328
    :try_start_0
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopProcessLocked()V

    .line 329
    monitor-exit p0

    .line 330
    return-void

    .line 329
    :catchall_0
    move-exception v0

    monitor-exit p0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    throw v0
.end method

.method private static stopProcessLocked()V
    .locals 4

    .line 333
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    if-eqz v0, :cond_3

    .line 335
    const/4 v0, 0x0

    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroy()V

    .line 336
    const/4 v1, 0x0

    :goto_0
    const/16 v2, 0xa

    if-ge v1, v2, :cond_1

    .line 337
    sget-object v2, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v2

    if-nez v2, :cond_0

    .line 338
    goto :goto_1

    .line 340
    :cond_0
    const-wide/16 v2, 0x1e

    invoke-static {v2, v3}, Ljava/lang/Thread;->sleep(J)V

    .line 336
    add-int/lit8 v1, v1, 0x1

    goto :goto_0

    .line 342
    :cond_1
    :goto_1
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    if-eqz v1, :cond_2

    .line 343
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-virtual {v1}, Ljava/lang/Process;->destroyForcibly()Ljava/lang/Process;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    goto :goto_2

    .line 345
    :catchall_0
    move-exception v1

    .line 347
    :cond_2
    :goto_2
    sput-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    .line 348
    nop

    .line 350
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

    .line 567
    invoke-virtual {p0}, Landroid/content/Context;->getAssets()Landroid/content/res/AssetManager;

    move-result-object v0

    .line 568
    const-string v1, "inubackend/version.txt"

    invoke-static {v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readAssetText(Landroid/content/res/AssetManager;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v1

    .line 569
    new-instance v2, Ljava/io/File;

    const-string v3, "version.txt"

    invoke-direct {v2, p1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 570
    new-instance p1, Ljava/io/File;

    const-string v3, "emulator.py"

    invoke-direct {p1, p3, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 571
    new-instance v3, Ljava/io/File;

    const-string v4, "stdlib.zip"

    invoke-direct {v3, p2, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 572
    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v4

    if-eqz v4, :cond_0

    invoke-virtual {p1}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    invoke-virtual {v3}, Ljava/io/File;->exists()Z

    move-result p1

    if-eqz p1, :cond_0

    .line 573
    invoke-static {v2}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->readFileText(Ljava/io/File;)Ljava/lang/String;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 574
    invoke-virtual {v1, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result p1

    if-eqz p1, :cond_0

    .line 575
    return-void

    .line 578
    :cond_0
    new-instance p1, Ljava/lang/StringBuilder;

    invoke-direct {p1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v4, "Unpacking embedded Python stdlib & emulator server bundle ("

    invoke-virtual {p1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    const-string v4, ")"

    invoke-virtual {p1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    const-string v4, "InuStandalone"

    invoke-static {v4, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 579
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->getClientOtaDir(Landroid/content/Context;)Ljava/io/File;

    move-result-object p0

    .line 580
    new-instance p1, Ljava/io/File;

    const-string v4, "src"

    invoke-direct {p1, p0, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-static {p1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->deleteRecursive(Ljava/io/File;)V

    .line 581
    new-instance p1, Ljava/io/File;

    const-string v4, "res"

    invoke-direct {p1, p0, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-static {p1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->deleteRecursive(Ljava/io/File;)V

    .line 582
    invoke-virtual {p2}, Ljava/io/File;->mkdirs()Z

    .line 583
    invoke-virtual {p3}, Ljava/io/File;->mkdirs()Z

    .line 585
    const-string p0, "inubackend/stdlib.zip"

    invoke-static {v0, p0, v3}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->copyAssetToFile(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/io/File;)V

    .line 586
    const-string p0, "inubackend/server_bundle.zip"

    invoke-virtual {v0, p0}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;

    move-result-object p0

    .line 587
    :try_start_0
    new-instance p1, Ljava/util/zip/ZipInputStream;

    invoke-direct {p1, p0}, Ljava/util/zip/ZipInputStream;-><init>(Ljava/io/InputStream;)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_4

    .line 589
    const p2, 0x8000

    :try_start_1
    new-array p2, p2, [B

    .line 590
    :goto_0
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->getNextEntry()Ljava/util/zip/ZipEntry;

    move-result-object v0

    if-eqz v0, :cond_4

    .line 591
    new-instance v3, Ljava/io/File;

    invoke-virtual {v0}, Ljava/util/zip/ZipEntry;->getName()Ljava/lang/String;

    move-result-object v4

    invoke-direct {v3, p3, v4}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 592
    invoke-virtual {v0}, Ljava/util/zip/ZipEntry;->isDirectory()Z

    move-result v0

    if-eqz v0, :cond_1

    .line 593
    invoke-virtual {v3}, Ljava/io/File;->mkdirs()Z

    goto :goto_2

    .line 595
    :cond_1
    invoke-virtual {v3}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 596
    if-eqz v0, :cond_2

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v4

    if-nez v4, :cond_2

    .line 597
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 599
    :cond_2
    new-instance v0, Ljava/io/File;

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

    invoke-direct {v0, v4, v5}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 600
    new-instance v4, Ljava/io/FileOutputStream;

    invoke-direct {v4, v0}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_2

    .line 602
    :goto_1
    :try_start_2
    invoke-virtual {p1, p2}, Ljava/util/zip/ZipInputStream;->read([B)I

    move-result v5

    if-lez v5, :cond_3

    .line 603
    const/4 v6, 0x0

    invoke-virtual {v4, p2, v6, v5}, Ljava/io/FileOutputStream;->write([BII)V
    :try_end_2
    .catchall {:try_start_2 .. :try_end_2} :catchall_0

    goto :goto_1

    .line 605
    :cond_3
    :try_start_3
    invoke-virtual {v4}, Ljava/io/FileOutputStream;->close()V

    .line 606
    invoke-virtual {v0, v3}, Ljava/io/File;->renameTo(Ljava/io/File;)Z

    .line 608
    :goto_2
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->closeEntry()V
    :try_end_3
    .catchall {:try_start_3 .. :try_end_3} :catchall_2

    .line 609
    goto :goto_0

    .line 600
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

    .line 610
    :cond_4
    :try_start_6
    invoke-virtual {p1}, Ljava/util/zip/ZipInputStream;->close()V
    :try_end_6
    .catchall {:try_start_6 .. :try_end_6} :catchall_4

    if-eqz p0, :cond_5

    invoke-virtual {p0}, Ljava/io/InputStream;->close()V

    .line 611
    :cond_5
    invoke-static {v2, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->writeFileText(Ljava/io/File;Ljava/lang/String;)V

    .line 612
    return-void

    .line 586
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

    .line 309
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;

    move-result-object p0

    .line 310
    sget-boolean v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->activityActive:Z

    if-eqz v0, :cond_0

    .line 312
    sget-object v0, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->LOCK:Ljava/lang/Object;

    monitor-enter v0

    .line 313
    :try_start_0
    sget-object v1, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->backendProcess:Ljava/lang/Process;

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isProcessAlive(Ljava/lang/Process;)Z

    move-result v1

    .line 314
    monitor-exit v0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 315
    if-nez v1, :cond_0

    const/16 v0, 0x12c

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z

    move-result v0

    if-nez v0, :cond_0

    .line 316
    const-string v0, "InuStandalone"

    const-string v1, "Watchdog detected stopped backend while game active; restarting"

    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 317
    const-wide/16 v0, 0x3a98

    invoke-static {p0, v0, v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;J)V

    goto :goto_0

    .line 314
    :catchall_0
    move-exception p0

    :try_start_1
    monitor-exit v0
    :try_end_1
    .catchall {:try_start_1 .. :try_end_1} :catchall_0

    throw p0

    .line 320
    :cond_0
    :goto_0
    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 321
    return-void
.end method

.method private static writeFileText(Ljava/io/File;Ljava/lang/String;)V
    .locals 2
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/io/IOException;
        }
    .end annotation

    .line 667
    invoke-virtual {p0}, Ljava/io/File;->getParentFile()Ljava/io/File;

    move-result-object v0

    .line 668
    if-eqz v0, :cond_0

    invoke-virtual {v0}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_0

    .line 669
    invoke-virtual {v0}, Ljava/io/File;->mkdirs()Z

    .line 671
    :cond_0
    new-instance v0, Ljava/io/FileOutputStream;

    invoke-direct {v0, p0}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V

    .line 672
    :try_start_0
    sget-object p0, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;

    invoke-virtual {p1, p0}, Ljava/lang/String;->getBytes(Ljava/nio/charset/Charset;)[B

    move-result-object p0

    invoke-virtual {v0, p0}, Ljava/io/FileOutputStream;->write([B)V
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 673
    invoke-virtual {v0}, Ljava/io/FileOutputStream;->close()V

    .line 674
    return-void

    .line 671
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
