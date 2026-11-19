.class Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;
.super Ljava/lang/Object;
.source "LocalBackendManager.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingMethod;
    value = Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onActivityPause(Landroid/content/Context;)V
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x0
    name = null
.end annotation


# instance fields
.field final synthetic val$appCtx:Landroid/content/Context;


# direct methods
.method constructor <init>(Landroid/content/Context;)V
    .locals 0
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "()V"
        }
    .end annotation

    .line 158
    iput-object p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;->val$appCtx:Landroid/content/Context;

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public run()V
    .locals 1

    .line 161
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$3;->val$appCtx:Landroid/content/Context;

    invoke-static {v0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->mirrorSaves(Landroid/content/Context;)V

    .line 162
    return-void
.end method
