.class Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;
.super Ljava/lang/Object;
.source "LocalBackendManager.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingMethod;
    value = Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onActivityDestroy(Landroid/content/Context;)V
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x0
    name = null
.end annotation


# instance fields
.field final synthetic val$appCtx:Landroid/content/Context;

.field final synthetic val$destroyStamp:J


# direct methods
.method constructor <init>(Landroid/content/Context;J)V
    .locals 0
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "()V"
        }
    .end annotation

    .line 258
    iput-object p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;->val$appCtx:Landroid/content/Context;

    iput-wide p2, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;->val$destroyStamp:J

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public run()V
    .locals 5

    .line 261
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;->val$appCtx:Landroid/content/Context;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 263
    const-wide/16 v0, 0xdac

    :try_start_0
    invoke-static {v0, v1}, Ljava/lang/Thread;->sleep(J)V
    :try_end_0
    .catch Ljava/lang/InterruptedException; {:try_start_0 .. :try_end_0} :catch_0

    .line 264
    :goto_0
    goto :goto_1

    :catch_0
    move-exception v0

    goto :goto_0

    .line 265
    :goto_1
    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->access$000()Z

    move-result v0

    if-nez v0, :cond_0

    invoke-static {}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->access$100()J

    move-result-wide v0

    iget-wide v2, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;->val$destroyStamp:J

    cmp-long v4, v0, v2

    if-nez v4, :cond_0

    .line 266
    const-string v0, "InuStandalone"

    const-string v1, "Activity closed; stopping embedded backend cleanly"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 267
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$5;->val$appCtx:Landroid/content/Context;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->stopBackend(Landroid/content/Context;)V

    .line 269
    :cond_0
    return-void
.end method
