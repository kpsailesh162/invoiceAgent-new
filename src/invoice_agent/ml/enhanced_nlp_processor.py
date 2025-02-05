from typing import Dict, Any, List, Optional
import spacy
from transformers import pipeline
import re
from datetime import datetime
import logging
from .ocr_processor import OCRResult
from .ner_trainer import InvoiceNERTrainer
import langdetect
from deep_translator import GoogleTranslator
import json
from pathlib import Path

class EnhancedNLPProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        
        # Load language-specific models
        self.language_models = self._load_language_models()
        
        # Load custom NER model
        self.custom_ner = self._load_custom_ner(config)
        
        # Initialize translator
        self.translator = GoogleTranslator(source='auto', target='en')
        
        # Load field validation rules
        self.validation_rules = self._load_validation_rules()
        
        # Initialize active learning component
        self.active_learning = ActiveLearningComponent(config)
    
    def _load_language_models(self) -> Dict[str, Any]:
        """Load spaCy models for different languages"""
        return {
            'en': spacy.load('en_core_web_lg'),
            'de': spacy.load('de_core_news_lg'),
            'fr': spacy.load('fr_core_news_lg'),
            'es': spacy.load('es_core_news_lg')
        }
    
    def _load_custom_ner(self, config: Dict[str, Any]) -> pipeline:
        """Load custom NER model"""
        model_path = config.get('custom_ner_model_path')
        if model_path and Path(model_path).exists():
            return pipeline(
                'ner',
                model=model_path,
                tokenizer=model_path
            )
        return None
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load field validation rules"""
        rules_path = Path('config/validation_rules.json')
        if rules_path.exists():
            with open(rules_path) as f:
                return json.load(f)
        return {}
    
    async def process_document(
        self,
        ocr_results: List[OCRResult],
        feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process document with enhanced NLP"""
        try:
            # Combine text while preserving layout
            processed_text = self._combine_text(ocr_results)
            
            # Detect language
            lang = langdetect.detect(processed_text)
            
            # Translate if not English
            if lang != 'en':
                translated_text = self.translator.translate(processed_text)
            else:
                translated_text = processed_text
            
            # Extract fields using custom NER
            if self.custom_ner:
                custom_entities = self.custom_ner(translated_text)
                extracted_data = self._process_custom_entities(custom_entities)
            else:
                # Fallback to pattern matching
                extracted_data = self._extract_fields_with_patterns(
                    translated_text,
                    lang
                )
            
            # Extract table structure
            tables = self._extract_tables(ocr_results)
            if tables:
                extracted_data['line_items'] = tables
            
            # Validate extracted data
            validation_results = self._validate_fields(extracted_data)
            if not validation_results['is_valid']:
                self.logger.warning(
                    f"Validation failed: {validation_results['errors']}"
                )
            
            # Update active learning component
            if feedback:
                await self.active_learning.update(
                    processed_text,
                    extracted_data,
                    feedback
                )
            
            return {
                'extracted_data': extracted_data,
                'validation_results': validation_results,
                'language': lang,
                'confidence_scores': self._calculate_confidence_scores(
                    extracted_data
                )
            }
            
        except Exception as e:
            self.logger.error(f"Enhanced NLP processing failed: {str(e)}")
            raise
    
    def _extract_tables(self, ocr_results: List[OCRResult]) -> List[Dict[str, Any]]:
        """Extract table structures from document"""
        try:
            # Group results by vertical position (rows)
            rows = self._group_by_rows(ocr_results)
            
            # Identify table headers
            header_row = self._identify_header_row(rows)
            if not header_row:
                return []
            
            # Map columns to fields
            column_mapping = self._map_columns_to_fields(header_row)
            
            # Extract line items
            line_items = []
            for row in rows:
                if row != header_row:
                    item = self._process_table_row(row, column_mapping)
                    if item:
                        line_items.append(item)
            
            return line_items
        except Exception as e:
            self.logger.error(f"Table extraction failed: {str(e)}")
            return []
    
    def _validate_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted fields against rules"""
        errors = []
        
        for field, rules in self.validation_rules.items():
            if field in data:
                value = data[field]
                
                for rule in rules:
                    if not self._check_rule(value, rule):
                        errors.append({
                            'field': field,
                            'rule': rule['type'],
                            'message': rule['message']
                        })
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def _check_rule(self, value: Any, rule: Dict[str, Any]) -> bool:
        """Check if value passes validation rule"""
        rule_type = rule['type']
        
        if rule_type == 'required':
            return value is not None and str(value).strip() != ''
        
        elif rule_type == 'regex':
            return bool(re.match(rule['pattern'], str(value)))
        
        elif rule_type == 'range':
            try:
                num_value = float(value)
                return rule['min'] <= num_value <= rule['max']
            except (ValueError, TypeError):
                return False
        
        elif rule_type == 'length':
            return rule['min'] <= len(str(value)) <= rule['max']
        
        elif rule_type == 'enum':
            return str(value) in rule['values']
        
        return True

class ActiveLearningComponent:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.trainer = InvoiceNERTrainer(config)
        self.feedback_threshold = config.get('feedback_threshold', 100)
        self.feedback_data = []
    
    async def update(
        self,
        text: str,
        predictions: Dict[str, Any],
        feedback: Dict[str, Any]
    ):
        """Update model with feedback"""
        try:
            # Store feedback
            self.feedback_data.append({
                'text': text,
                'predictions': predictions,
                'corrections': feedback
            })
            
            # Check if we should retrain
            if len(self.feedback_data) >= self.feedback_threshold:
                await self._retrain_model()
                
        except Exception as e:
            self.logger.error(f"Active learning update failed: {str(e)}")
    
    async def _retrain_model(self):
        """Retrain model with accumulated feedback"""
        try:
            # Prepare training data
            training_data = self._prepare_training_data()
            
            # Train model
            output_dir = self.config['model_output_dir']
            self.trainer.train(training_data, output_dir)
            
            # Clear feedback data
            self.feedback_data = []
            
        except Exception as e:
            self.logger.error(f"Model retraining failed: {str(e)}")
    
    def _prepare_training_data(self) -> List[Dict[str, Any]]:
        """Convert feedback data to training format"""
        training_data = []
        
        for item in self.feedback_data:
            annotations = []
            for field, value in item['corrections'].items():
                if isinstance(value, str):
                    # Find position of value in text
                    start = item['text'].find(value)
                    if start != -1:
                        annotations.append({
                            'start': start,
                            'end': start + len(value),
                            'label': field
                        })
            
            training_data.append({
                'text': item['text'],
                'annotations': annotations
            })
        
        return training_data 