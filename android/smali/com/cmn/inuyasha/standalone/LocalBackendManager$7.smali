.class Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;
.super Ljava/lang/Object;
.source "LocalBackendManager.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingMethod;
    value = Lcom/cmn/inuyasha/standalone/LocalBackendManager;->isLoopbackHealthy(I)Z
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x0
    name = null
.end annotation


# instance fields
.field final synthetic val$ok:[Z

.field final synthetic val$timeoutMs:I


# direct methods
.method constructor <init>([ZI)V
    .locals 0
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "()V"
        }
    .end annotation

    .line 367
    iput-object p1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;->val$ok:[Z

    iput p2, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;->val$timeoutMs:I

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public run()V
    .locals 3

    .line 370
    iget-object v0, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;->val$ok:[Z

    iget v1, p0, Lcom/cmn/inuyasha/standalone/LocalBackendManager$7;->val$timeoutMs:I

    invoke-static {v1}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->access$300(I)Z

    move-result v1

    const/4 v2, 0x0

    aput-boolean v1, v0, v2

    .line 371
    return-void
.end method
