"""CLI 主入口."""

from __future__ import annotations

import typer
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging

app = typer.Typer(help="古建筑游客兴趣分析系统 CLI")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
) -> None:
    """Building Analysis CLI."""
    setup_logging(level="DEBUG" if verbose else "INFO")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="绑定主机"),
    port: int = typer.Option(8000, "--port", "-p", help="绑定端口"),
    reload: bool = typer.Option(False, "--reload", "-r", help="热重载"),
) -> None:
    """启动 API 服务."""
    import uvicorn
    
    logger.info(f"Starting server at http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def train_svm(
    tune: bool = typer.Option(True, "--tune/--no-tune", help="超参数调优"),
) -> None:
    """训练 SVM 情感分析模型."""
    from ml.sentiment_svm import SVMTrainer, generate_sample_data
    
    settings = get_settings()
    
    logger.info("Starting SVM training...")
    texts, labels = generate_sample_data()
    
    trainer = SVMTrainer(settings.model_dir)
    X_train, X_test, y_train, y_test = trainer.prepare_data(texts, labels)
    trainer.train(X_train, y_train, tune_hyperparams=tune)
    
    metrics = trainer.evaluate(X_test, y_test)
    logger.info(f"Metrics: {metrics.model_dump()}")
    
    trainer.save()
    logger.success("SVM training completed!")


@app.command()
def train_vlm(
    epochs: int = typer.Option(50, "--epochs", "-e", help="训练轮数"),
    batch_size: int = typer.Option(32, "--batch-size", "-b", help="批次大小"),
) -> None:
    """训练 VLM 模型."""
    logger.info("VLM training - requires prepared dataset")
    logger.info(f"Config: epochs={epochs}, batch_size={batch_size}")
    # 实际训练逻辑在 ml.vlm_trainer 中


@app.command()
def analyze(
    html_dir: str = typer.Option(None, "--html-dir", help="HTML 文件目录"),
    skip_vlm: bool = typer.Option(False, "--skip-vlm", help="跳过 VLM 分类"),
) -> None:
    """运行完整分析流程."""
    from app.services.analysis.sentiment import SentimentService
    from app.services.analysis.vlm_classifier import VLMService
    from app.services.importers.xhs_html import XHSHTMLImporter
    
    settings = get_settings()
    
    # 1. 导入
    logger.info("Step 1: Importing HTML...")
    importer = XHSHTMLImporter()
    notes = importer.run()
    logger.info(f"Imported {len(notes)} notes")
    
    # 2. 情感分析
    logger.info("Step 2: Sentiment Analysis...")
    sentiment_svc = SentimentService()
    sentiment_summary = sentiment_svc.run()
    logger.info(f"Sentiment: {sentiment_summary}")
    
    # 3. VLM 分类
    if not skip_vlm:
        logger.info("Step 3: VLM Classification...")
        vlm_svc = VLMService()
        predictions = vlm_svc.run()
        logger.info(f"Classified {len(predictions)} images")
    
    logger.success("Analysis completed!")


if __name__ == "__main__":
    app()
