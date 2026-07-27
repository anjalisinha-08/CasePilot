"""
CasePilot 2.0 — Model Evaluator
==================================
Compares fraud predictions (from fraud_scorer) against ground truth
(IS_FRAUD column) to calculate confusion matrix and performance metrics.

Metrics are stored per-run in ANALYTICS.MODEL_METRICS for trend tracking.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from src.utils.helpers import generate_uuid, safe_divide

logger = logging.getLogger(__name__)


def evaluate_model(
    predictions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate confusion matrix and classification metrics.

    Each prediction dict must have:
        - is_fraud (bool): Ground truth label
        - is_predicted_fraud (bool): Model prediction

    Returns:
        Dict with TP, TN, FP, FN, accuracy, precision, recall, F1, FPR, FNR.
    """
    tp = tn = fp = fn = 0

    for pred in predictions:
        actual = bool(pred.get("is_fraud", False))
        predicted = bool(pred.get("is_predicted_fraud", False))

        if actual and predicted:
            tp += 1
        elif not actual and not predicted:
            tn += 1
        elif not actual and predicted:
            fp += 1
        else:  # actual and not predicted
            fn += 1

    total = tp + tn + fp + fn
    accuracy = safe_divide(tp + tn, total)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    fpr = safe_divide(fp, fp + tn)
    fnr = safe_divide(fn, fn + tp)

    run_id = generate_uuid()

    result = {
        "METRIC_ID": generate_uuid(),
        "RUN_ID": run_id,
        "MODEL_VERSION": "2.0",
        "TOTAL_PREDICTIONS": total,
        "TRUE_POSITIVES": tp,
        "TRUE_NEGATIVES": tn,
        "FALSE_POSITIVES": fp,
        "FALSE_NEGATIVES": fn,
        "ACCURACY": round(accuracy, 6),
        "PRECISION_SCORE": round(precision, 6),
        "RECALL": round(recall, 6),
        "F1_SCORE": round(f1, 6),
        "FALSE_POSITIVE_RATE": round(fpr, 6),
        "FALSE_NEGATIVE_RATE": round(fnr, 6),
        "EVALUATION_DETAILS": {
            "confusion_matrix": {
                "true_positive": tp,
                "true_negative": tn,
                "false_positive": fp,
                "false_negative": fn,
            },
            "class_distribution": {
                "actual_fraud": tp + fn,
                "actual_legit": tn + fp,
                "predicted_fraud": tp + fp,
                "predicted_legit": tn + fn,
            },
        },
        "EVALUATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    logger.info(
        f"Model evaluation complete — "
        f"Accuracy: {result['ACCURACY']:.4f}, "
        f"Precision: {result['PRECISION_SCORE']:.4f}, "
        f"Recall: {result['RECALL']:.4f}, "
        f"F1: {result['F1_SCORE']:.4f} | "
        f"TP={tp} TN={tn} FP={fp} FN={fn}"
    )

    return result


def insert_metrics_to_snowflake(metrics: Dict[str, Any], connection) -> int:
    """Store evaluation metrics in ANALYTICS.MODEL_METRICS."""
    insert_sql = """
        INSERT INTO CASEPILOT_DB.ANALYTICS.MODEL_METRICS (
            METRIC_ID, RUN_ID, MODEL_VERSION, TOTAL_PREDICTIONS,
            TRUE_POSITIVES, TRUE_NEGATIVES, FALSE_POSITIVES, FALSE_NEGATIVES,
            ACCURACY, PRECISION_SCORE, RECALL, F1_SCORE,
            FALSE_POSITIVE_RATE, FALSE_NEGATIVE_RATE,
            EVALUATION_DETAILS, EVALUATED_AT
        )
        SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
               PARSE_JSON(%s), %s
    """
    cursor = connection.get_connection().cursor()
    try:
        cursor.execute(insert_sql, (
            metrics["METRIC_ID"], metrics["RUN_ID"], metrics["MODEL_VERSION"],
            metrics["TOTAL_PREDICTIONS"],
            metrics["TRUE_POSITIVES"], metrics["TRUE_NEGATIVES"],
            metrics["FALSE_POSITIVES"], metrics["FALSE_NEGATIVES"],
            metrics["ACCURACY"], metrics["PRECISION_SCORE"],
            metrics["RECALL"], metrics["F1_SCORE"],
            metrics["FALSE_POSITIVE_RATE"], metrics["FALSE_NEGATIVE_RATE"],
            json.dumps(metrics["EVALUATION_DETAILS"]),
            metrics["EVALUATED_AT"],
        ))
    finally:
        cursor.close()

    logger.info("Stored model metrics in Snowflake.")
    return 1
