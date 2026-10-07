"""Explicit local LoRA fine-tuning from approved Echo model-team examples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_approved_examples(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Approved training data not found: {path}")
    examples: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            prompt = record.get("prompt")
            response = record.get("response")
            if isinstance(prompt, str) and prompt.strip() and isinstance(response, str) and response.strip():
                examples.append({"prompt": prompt.strip(), "response": response.strip()})
    if not examples:
        raise ValueError("Approved training data contains no usable prompt/response examples.")
    return examples


def train_adapter(
    base_model: Path,
    output_dir: Path,
    data_file: Path,
    *,
    target_modules: list[str],
    max_length: int = 512,
) -> None:
    """Train and save a new LoRA adapter; the configured base checkpoint is not overwritten."""
    if not base_model.is_dir():
        raise NotADirectoryError(f"Base model must be a local Hugging Face checkpoint directory: {base_model}")
    if output_dir.resolve() == base_model.resolve() or base_model.resolve() in output_dir.resolve().parents:
        raise ValueError("Adapter output must be outside the base model directory.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Adapter output directory must be empty: {output_dir}")
    if not target_modules:
        raise ValueError("At least one model target module must be configured.")
    if not 32 <= max_length <= 4096:
        raise ValueError("max_length must be between 32 and 4096.")
    examples = load_approved_examples(data_file)

    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from torch.utils.data import Dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling, Trainer, TrainingArguments
    except ImportError as exc:
        raise RuntimeError(
            "Training extras are missing. Install the optional packages from requirements-training.txt."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(str(base_model), local_files_only=True, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(base_model),
        local_files_only=True,
        trust_remote_code=False,
    )
    model = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=target_modules,
            task_type="CAUSAL_LM",
        ),
    )

    class ApprovedDataset(Dataset):
        def __len__(self) -> int:
            return len(examples)

        def __getitem__(self, index: int) -> dict[str, Any]:
            example = examples[index]
            text = f"### User:\n{example['prompt']}\n\n### Assistant:\n{example['response']}{tokenizer.eos_token}"
            return tokenizer(text, truncation=True, max_length=max_length)

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=1,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            logging_steps=5,
            save_strategy="epoch",
            save_total_limit=2,
            report_to=[],
            fp16=torch.cuda.is_available(),
        ),
        train_dataset=ApprovedDataset(),
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", required=True, type=Path, help="Local Hugging Face checkpoint directory")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for the LoRA adapter")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "echo_model_team" / "approved.jsonl",
    )
    parser.add_argument(
        "--target-modules",
        default="q_proj,k_proj,v_proj,o_proj",
        help="Comma-separated attention projection module names for the selected model architecture",
    )
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()
    if not 32 <= args.max_length <= 4096:
        parser.error("--max-length must be between 32 and 4096")
    train_adapter(
        args.base_model,
        args.output_dir,
        args.data_file,
        target_modules=[item.strip() for item in args.target_modules.split(",") if item.strip()],
        max_length=args.max_length,
    )


if __name__ == "__main__":
    main()
