from typing import Dict, Any, List, Callable
import re
from decimal import Decimal
from ..core.data_model import Invoice

class ValidationRule:
    def __init__(self, field: str, rule_type: str, params: Dict[str, Any]):
        self.field = field
        self.rule_type = rule_type
        self.params = params
    
    def validate(self, value: Any) -> bool:
        if self.rule_type == 'required':
            return value is not None and str(value).strip() != ''
        elif self.rule_type == 'regex':
            return bool(re.match(self.params['pattern'], str(value)))
        elif self.rule_type == 'range':
            return self.params['min'] <= Decimal(str(value)) <= self.params['max']
        return True

class RuleEngine:
    def __init__(self, rules_config: Dict[str, Any]):
        self.rules = self._build_rules(rules_config)
    
    def _build_rules(self, config: Dict[str, Any]) -> List[ValidationRule]:
        rules = []
        for field, field_rules in config.items():
            for rule_type, params in field_rules.items():
                rules.append(ValidationRule(field, rule_type, params))
        return rules
    
    def validate_invoice(self, invoice: Invoice) -> Dict[str, List[str]]:
        errors = {}
        
        for rule in self.rules:
            value = self._get_field_value(invoice, rule.field)
            if not rule.validate(value):
                if rule.field not in errors:
                    errors[rule.field] = []
                errors[rule.field].append(
                    f"Failed {rule.rule_type} validation"
                )
        
        return errors
    
    def _get_field_value(self, invoice: Invoice, field: str) -> Any:
        if hasattr(invoice, field):
            return getattr(invoice, field)
        return invoice.additional_fields.get(field) 