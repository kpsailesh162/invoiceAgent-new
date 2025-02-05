from typing import List, Dict, Any, Tuple, Optional
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
    IntervalStrategy
)
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import json
import logging
from pathlib import Path
import mlflow
import optuna
from tqdm import tqdm
from datetime import datetime

class EnhancedInvoiceNERDataset(Dataset):
    def __init__(
        self,
        texts: List[str],
        labels: List[List[str]],
        tokenizer: AutoTokenizer,
        max_length: int = 512
    ):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.label2id = self._create_label_map()
        self.id2label = {v: k for k, v in self.label2id.items()}
        
    def _create_label_map(self) -> Dict[str, int]:
        """Create label to ID mapping with special tokens"""
        unique_labels = sorted(list(set(
            label for seq in self.labels for label in seq
        )))
        label_map = {
            'PAD': 0,  # Padding token
            'UNK': 1,  # Unknown token
            'O': 2     # Outside token
        }
        for label in unique_labels:
            if label not in label_map:
                label_map[label] = len(label_map)
        return label_map
    
    def __len__(self) -> int:
        return len(self.texts)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        text = self.texts[idx]
        label_seq = self.labels[idx]
        
        # Tokenize with word-to-token alignment
        encoding = self.tokenizer(
            text.split(),
            is_split_into_words=True,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt',
            return_offsets_mapping=True,
            return_special_tokens_mask=True
        )
        
        # Align labels with tokens
        aligned_labels = self._align_labels_with_tokens(
            label_seq,
            encoding.offset_mapping[0],
            encoding.special_tokens_mask[0]
        )
        
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(aligned_labels),
            'original_text': text,
            'original_labels': label_seq
        }
    
    def _align_labels_with_tokens(
        self,
        labels: List[str],
        offset_mapping: torch.Tensor,
        special_tokens_mask: torch.Tensor
    ) -> List[int]:
        """Align labels with tokenized input"""
        aligned_labels = []
        current_label_idx = 0
        
        for idx, (offset, is_special) in enumerate(zip(
            offset_mapping, special_tokens_mask
        )):
            if is_special:
                aligned_labels.append(self.label2id['PAD'])
                continue
                
            if offset[0] == offset[1]:  # Empty token
                aligned_labels.append(self.label2id['PAD'])
                continue
                
            try:
                aligned_labels.append(self.label2id[labels[current_label_idx]])
            except IndexError:
                aligned_labels.append(self.label2id['O'])
            except KeyError:
                aligned_labels.append(self.label2id['UNK'])
                
            current_label_idx += 1
            
        return aligned_labels

class EnhancedInvoiceNERTrainer:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.model_name = config.get('model_name', 'bert-base-multilingual-cased')
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = None
        self.best_model_path = None
        
        # MLflow setup
        mlflow.set_tracking_uri(config.get('mlflow_tracking_uri', 'mlruns'))
        self.experiment_name = config.get('experiment_name', 'invoice_ner')
        mlflow.set_experiment(self.experiment_name)
        
    def train(
        self,
        training_data: List[Dict[str, Any]],
        output_dir: str,
        do_hyperparameter_search: bool = True
    ):
        """Train custom NER model with optional hyperparameter optimization"""
        try:
            # Prepare data
            texts, labels = self._prepare_training_data(training_data)
            train_texts, val_texts, train_labels, val_labels = train_test_split(
                texts, labels, test_size=0.2, random_state=42
            )
            
            # Create datasets
            train_dataset = EnhancedInvoiceNERDataset(
                train_texts,
                train_labels,
                self.tokenizer
            )
            val_dataset = EnhancedInvoiceNERDataset(
                val_texts,
                val_labels,
                self.tokenizer
            )
            
            if do_hyperparameter_search:
                best_params = self._hyperparameter_optimization(
                    train_dataset,
                    val_dataset
                )
            else:
                best_params = self.config.get('training_params', {})
            
            with mlflow.start_run():
                # Log parameters
                mlflow.log_params(best_params)
                
                # Initialize model
                self.model = AutoModelForTokenClassification.from_pretrained(
                    self.model_name,
                    num_labels=len(train_dataset.label2id),
                    id2label=train_dataset.id2label,
                    label2id=train_dataset.label2id
                )
                
                # Training arguments
                training_args = TrainingArguments(
                    output_dir=output_dir,
                    num_train_epochs=best_params.get('num_train_epochs', 3),
                    per_device_train_batch_size=best_params.get(
                        'batch_size', 16
                    ),
                    per_device_eval_batch_size=best_params.get(
                        'batch_size', 16
                    ),
                    learning_rate=best_params.get('learning_rate', 2e-5),
                    weight_decay=best_params.get('weight_decay', 0.01),
                    warmup_ratio=best_params.get('warmup_ratio', 0.1),
                    evaluation_strategy=IntervalStrategy.STEPS,
                    eval_steps=100,
                    logging_steps=50,
                    save_strategy=IntervalStrategy.STEPS,
                    save_steps=100,
                    load_best_model_at_end=True,
                    metric_for_best_model='eval_f1',
                    greater_is_better=True
                )
                
                # Initialize trainer with callbacks
                trainer = Trainer(
                    model=self.model,
                    args=training_args,
                    train_dataset=train_dataset,
                    eval_dataset=val_dataset,
                    compute_metrics=self._compute_metrics,
                    callbacks=[
                        EarlyStoppingCallback(
                            early_stopping_patience=3,
                            early_stopping_threshold=0.01
                        )
                    ]
                )
                
                # Train model
                train_result = trainer.train()
                
                # Log metrics
                mlflow.log_metrics(train_result.metrics)
                
                # Evaluate on validation set
                eval_results = trainer.evaluate()
                mlflow.log_metrics(eval_results)
                
                # Save best model
                self.best_model_path = f"{output_dir}/best_model"
                trainer.save_model(self.best_model_path)
                self.tokenizer.save_pretrained(self.best_model_path)
                
                # Save label mapping
                with open(f"{self.best_model_path}/label_map.json", 'w') as f:
                    json.dump(train_dataset.label2id, f)
                
                # Generate and save model card
                self._generate_model_card(
                    train_result.metrics,
                    eval_results,
                    best_params
                )
                
        except Exception as e:
            self.logger.error(f"Training failed: {str(e)}")
            raise
    
    def _hyperparameter_optimization(
        self,
        train_dataset: EnhancedInvoiceNERDataset,
        val_dataset: EnhancedInvoiceNERDataset
    ) -> Dict[str, Any]:
        """Perform hyperparameter optimization using Optuna"""
        def objective(trial):
            params = {
                'learning_rate': trial.suggest_float(
                    'learning_rate', 1e-5, 5e-5, log=True
                ),
                'batch_size': trial.suggest_categorical(
                    'batch_size', [8, 16, 32]
                ),
                'num_train_epochs': trial.suggest_int(
                    'num_train_epochs', 2, 5
                ),
                'weight_decay': trial.suggest_float(
                    'weight_decay', 0.01, 0.1, log=True
                ),
                'warmup_ratio': trial.suggest_float(
                    'warmup_ratio', 0.0, 0.2
                )
            }
            
            with mlflow.start_run(nested=True):
                mlflow.log_params(params)
                
                model = AutoModelForTokenClassification.from_pretrained(
                    self.model_name,
                    num_labels=len(train_dataset.label2id)
                )
                
                training_args = TrainingArguments(
                    output_dir=f"./temp_trainer_{trial.number}",
                    num_train_epochs=params['num_train_epochs'],
                    per_device_train_batch_size=params['batch_size'],
                    per_device_eval_batch_size=params['batch_size'],
                    learning_rate=params['learning_rate'],
                    weight_decay=params['weight_decay'],
                    warmup_ratio=params['warmup_ratio'],
                    evaluation_strategy='epoch',
                    logging_steps=50,
                    load_best_model_at_end=True
                )
                
                trainer = Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=train_dataset,
                    eval_dataset=val_dataset,
                    compute_metrics=self._compute_metrics
                )
                
                train_result = trainer.train()
                eval_results = trainer.evaluate()
                
                mlflow.log_metrics(eval_results)
                
                return eval_results['eval_f1']
        
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=10)
        
        return study.best_params
    
    def _compute_metrics(
        self,
        eval_pred: Tuple[np.ndarray, np.ndarray]
    ) -> Dict[str, float]:
        """Compute evaluation metrics"""
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=2)
        
        # Remove padding tokens
        true_predictions = [
            [self.model.config.id2label[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [self.model.config.id2label[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        
        # Calculate metrics
        results = classification_report(
            [l for label in true_labels for l in label],
            [p for pred in true_predictions for p in pred],
            output_dict=True
        )
        
        return {
            'precision': results['weighted avg']['precision'],
            'recall': results['weighted avg']['recall'],
            'f1': results['weighted avg']['f1-score']
        }
    
    def _generate_model_card(
        self,
        train_metrics: Dict[str, float],
        eval_metrics: Dict[str, float],
        params: Dict[str, Any]
    ):
        """Generate model card with training details"""
        model_card = f"""
# Invoice NER Model Card

## Model Details
- Model Architecture: {self.model_name}
- Training Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Version: {self.config.get('version', '1.0.0')}

## Training Parameters
{json.dumps(params, indent=2)}

## Performance Metrics
### Training Metrics
{json.dumps(train_metrics, indent=2)}

### Evaluation Metrics
{json.dumps(eval_metrics, indent=2)}

## Usage
This model is designed for Named Entity Recognition in invoice documents.
It can identify entities such as invoice numbers, dates, amounts, and vendor information.

## Limitations
- The model's performance may vary for invoices significantly different from the training data.
- Performance might be affected by poor quality scans or unusual formatting.
"""
        
        with open(f"{self.best_model_path}/model_card.md", 'w') as f:
            f.write(model_card)
    
    def _prepare_training_data(
        self,
        data: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[List[str]]]:
        """Prepare training data from annotated invoices"""
        texts = []
        labels = []
        
        for item in data:
            text = item['text']
            annotations = item['annotations']
            
            # Create label sequence
            text_labels = ['O'] * len(text.split())
            for annotation in annotations:
                start_idx = annotation['start']
                end_idx = annotation['end']
                label = annotation['label']
                
                # BIO tagging
                text_labels[start_idx] = f'B-{label}'
                for idx in range(start_idx + 1, end_idx):
                    text_labels[idx] = f'I-{label}'
            
            texts.append(text)
            labels.append(text_labels)
        
        return texts, labels 