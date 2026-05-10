"""
Fine-tune ProsusAI/finbert on the financial_phrasebank dataset.

Usage:
    python -m sentiment.finetune [--epochs 3] [--batch-size 16] [--output-dir ./finbert-finetuned]

The script:
  1. Loads financial_phrasebank (sentences_allagree split — highest agreement)
  2. Maps labels to 0=negative, 1=neutral, 2=positive
  3. Fine-tunes FinBERT using HuggingFace Trainer
  4. Evaluates with weighted F1 (handles class imbalance)
  5. Saves the model locally and optionally uploads to S3
"""
import argparse
import logging

import numpy as np
from datasets import load_dataset
from sklearn.metrics import f1_score, accuracy_score, classification_report
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)

from config.settings import SENTIMENT_MODEL_NAME, SENTIMENT_MODEL_VERSION

logger = logging.getLogger(__name__)

LABEL_MAP = {0: "positive", 1: "neutral", 2: "negative"}
NUM_LABELS = 3


def load_financial_phrasebank():
    ds = load_dataset(
        "takala/financial_phrasebank",
        "sentences_allagree",
        trust_remote_code=True,
    )
    ds = ds["train"].train_test_split(test_size=0.15, seed=42, stratify_by_column="label")
    return ds["train"], ds["test"]


def tokenize_dataset(dataset, tokenizer, max_length=512):
    def _tokenize(batch):
        return tokenizer(
            batch["sentence"],
            padding="max_length",
            truncation=True,
            max_length=max_length,
        )

    return dataset.map(_tokenize, batched=True, remove_columns=["sentence"])


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "weighted_f1": f1_score(labels, preds, average="weighted"),
        "macro_f1": f1_score(labels, preds, average="macro"),
    }


def finetune(
    base_model: str = SENTIMENT_MODEL_NAME,
    output_dir: str = "./finbert-finetuned",
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    warmup_ratio: float = 0.1,
    upload_s3: bool = False,
):
    logger.info("Loading tokenizer and model from %s", base_model)
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=NUM_LABELS,
        id2label=LABEL_MAP,
        label2id={v: k for k, v in LABEL_MAP.items()},
    )

    logger.info("Loading financial_phrasebank dataset")
    train_ds, eval_ds = load_financial_phrasebank()
    logger.info("Train: %d samples, Eval: %d samples", len(train_ds), len(eval_ds))

    train_ds = tokenize_dataset(train_ds, tokenizer)
    eval_ds = tokenize_dataset(eval_ds, tokenizer)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="weighted_f1",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=2,
        fp16=False,
        report_to="none",
        seed=42,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    logger.info("Starting fine-tuning for %d epochs", epochs)
    trainer.train()

    eval_results = trainer.evaluate()
    logger.info("Eval results: %s", eval_results)

    preds = trainer.predict(eval_ds)
    pred_labels = np.argmax(preds.predictions, axis=-1)
    report = classification_report(
        eval_ds["label"],
        pred_labels,
        target_names=list(LABEL_MAP.values()),
    )
    logger.info("Classification report:\n%s", report)

    final_dir = f"{output_dir}/final"
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)
    logger.info("Model saved to %s", final_dir)

    if upload_s3:
        from data.storage.s3_client import upload_model_dir
        s3_path = upload_model_dir(final_dir, SENTIMENT_MODEL_VERSION)
        logger.info("Model uploaded to %s", s3_path)

    return eval_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Fine-tune FinBERT on financial_phrasebank")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--output-dir", default="./finbert-finetuned")
    parser.add_argument("--upload-s3", action="store_true")
    args = parser.parse_args()

    results = finetune(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        output_dir=args.output_dir,
        upload_s3=args.upload_s3,
    )
    print(f"\nFinal weighted F1: {results['eval_weighted_f1']:.4f}")
