.class public final Lcom/cmn/inuyasha/standalone/LocalBackendService;
.super Landroid/app/Service;
.source "LocalBackendService.java"


# instance fields
.field private volatile running:Z

.field private watchdogThread:Ljava/lang/Thread;


# direct methods
.method public constructor <init>()V
    .locals 1

    .line 8
    invoke-direct {p0}, Landroid/app/Service;-><init>()V

    .line 9
    const/4 v0, 0x0

    iput-boolean v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    .line 10
    const/4 v0, 0x0

    iput-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    return-void
.end method

.method static synthetic access$000(Lcom/cmn/inuyasha/standalone/LocalBackendService;)Z
    .locals 0

    .line 8
    iget-boolean p0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    return p0
.end method


# virtual methods
.method public onBind(Landroid/content/Intent;)Landroid/os/IBinder;
    .locals 0

    .line 59
    const/4 p1, 0x0

    return-object p1
.end method

.method public onDestroy()V
    .locals 1

    .line 48
    const/4 v0, 0x0

    iput-boolean v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    .line 49
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    if-eqz v0, :cond_0

    .line 50
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    invoke-virtual {v0}, Ljava/lang/Thread;->interrupt()V

    .line 51
    const/4 v0, 0x0

    iput-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    .line 53
    :cond_0
    invoke-virtual {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendService;->getApplicationContext()Landroid/content/Context;

    move-result-object v0

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopBackend(Landroid/content/Context;)V

    .line 54
    invoke-super {p0}, Landroid/app/Service;->onDestroy()V

    .line 55
    return-void
.end method

.method public onStartCommand(Landroid/content/Intent;II)I
    .locals 1

    .line 14
    iget-boolean p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    if-nez p1, :cond_0

    .line 15
    const/4 p1, 0x1

    iput-boolean p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    .line 16
    new-instance p2, Ljava/lang/Thread;

    new-instance p3, Lcom/cmn/inuyasha/standalone/LocalBackendService$1;

    invoke-direct {p3, p0}, Lcom/cmn/inuyasha/standalone/LocalBackendService$1;-><init>(Lcom/cmn/inuyasha/standalone/LocalBackendService;)V

    const-string v0, "InuBackendWatchdog"

    invoke-direct {p2, p3, v0}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;Ljava/lang/String;)V

    iput-object p2, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    .line 31
    iget-object p2, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    invoke-virtual {p2, p1}, Ljava/lang/Thread;->setDaemon(Z)V

    .line 32
    iget-object p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->watchdogThread:Ljava/lang/Thread;

    invoke-virtual {p1}, Ljava/lang/Thread;->start()V

    .line 34
    :cond_0
    const/4 p1, 0x2

    return p1
.end method

.method public onTaskRemoved(Landroid/content/Intent;)V
    .locals 2

    .line 39
    const-string v0, "InuStandalone"

    const-string v1, "onTaskRemoved -> stopping embedded backend & mirroring saves"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 40
    const/4 v0, 0x0

    iput-boolean v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService;->running:Z

    .line 41
    invoke-virtual {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendService;->getApplicationContext()Landroid/content/Context;

    move-result-object v0

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopBackend(Landroid/content/Context;)V

    .line 42
    invoke-virtual {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendService;->stopSelf()V

    .line 43
    invoke-super {p0, p1}, Landroid/app/Service;->onTaskRemoved(Landroid/content/Intent;)V

    .line 44
    return-void
.end method
