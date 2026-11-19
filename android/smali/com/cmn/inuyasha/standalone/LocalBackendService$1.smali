.class Lcom/cmn/inuyasha/standalone/LocalBackendService$1;
.super Ljava/lang/Object;
.source "LocalBackendService.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingMethod;
    value = Lcom/cmn/inuyasha/standalone/LocalBackendService;->onStartCommand(Landroid/content/Intent;II)I
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x0
    name = null
.end annotation


# instance fields
.field final synthetic this$0:Lcom/cmn/inuyasha/standalone/LocalBackendService;


# direct methods
.method constructor <init>(Lcom/cmn/inuyasha/standalone/LocalBackendService;)V
    .locals 0
    .annotation system Ldalvik/annotation/MethodParameters;
        accessFlags = {
            0x8010
        }
        names = {
            null
        }
    .end annotation

    .line 16
    iput-object p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService$1;->this$0:Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public run()V
    .locals 3

    .line 19
    nop

    :goto_0
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService$1;->this$0:Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendService;->access$000(Lcom/cmn/inuyasha/standalone/LocalBackendService;)Z

    move-result v0

    if-eqz v0, :cond_0

    .line 21
    :try_start_0
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendService$1;->this$0:Lcom/cmn/inuyasha/standalone/LocalBackendService;

    invoke-virtual {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendService;->getApplicationContext()Landroid/content/Context;

    move-result-object v0

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->watchdogTick(Landroid/content/Context;)V

    .line 22
    const-wide/16 v0, 0xfa0

    invoke-static {v0, v1}, Ljava/lang/Thread;->sleep(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    goto :goto_1

    .line 25
    :catchall_0
    move-exception v0

    .line 26
    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "Watchdog error: "

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "InuStandalone"

    invoke-static {v1, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    .line 27
    :goto_1
    goto :goto_0

    .line 23
    :catch_0
    move-exception v0

    .line 24
    nop

    .line 29
    :cond_0
    return-void
.end method
