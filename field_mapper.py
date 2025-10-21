"""
Field mapping framework for normalizing extracted data to canonical schema.
Supports rules-based and manual field mappings per pattern cluster.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import re


class FieldMapper:
    """
    Maps source fields to canonical schema with transformation rules.
    """

    def __init__(self, mappings_file: Optional[str] = None):
        """
        Initialize field mapper.

        Args:
            mappings_file: Path to mappings JSON file (optional)
        """
        self.cluster_mappings = {}  # cluster_id -> {source_field -> canonical_field}
        self.transformation_rules = {}  # canonical_field -> transformation function
        self.canonical_schema = {}  # canonical_field -> field definition

        if mappings_file and Path(mappings_file).exists():
            self.load_mappings(mappings_file)

    def add_field_mapping(
        self,
        cluster_id: int,
        source_field: str,
        canonical_field: str,
        transformation: Optional[str] = None
    ):
        """
        Add a field mapping for a specific cluster.

        Args:
            cluster_id: Pattern cluster ID
            source_field: Source field name in Excel
            canonical_field: Target canonical field name
            transformation: Optional transformation rule name
        """
        if cluster_id not in self.cluster_mappings:
            self.cluster_mappings[cluster_id] = {}

        self.cluster_mappings[cluster_id][source_field] = {
            'canonical_field': canonical_field,
            'transformation': transformation
        }

    def define_canonical_field(
        self,
        field_name: str,
        field_type: str,
        description: str,
        required: bool = False,
        validation_rules: Optional[List[str]] = None
    ):
        """
        Define a canonical field in the target schema.

        Args:
            field_name: Canonical field name
            field_type: Field type (string, number, date, boolean)
            description: Field description
            required: Whether field is required
            validation_rules: Optional validation rules
        """
        self.canonical_schema[field_name] = {
            'type': field_type,
            'description': description,
            'required': required,
            'validation_rules': validation_rules or []
        }

    def add_transformation_rule(
        self,
        rule_name: str,
        transformation_func: Callable[[Any], Any]
    ):
        """
        Add a transformation function.

        Args:
            rule_name: Name of transformation rule
            transformation_func: Function that transforms value
        """
        self.transformation_rules[rule_name] = transformation_func

    def map_client_data(
        self,
        client_data: Dict[str, Any],
        cluster_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Map client data to canonical schema.

        Args:
            client_data: Original client data
            cluster_id: Pattern cluster ID (auto-detect if not provided)

        Returns:
            Mapped client data with canonical fields
        """
        if cluster_id is None:
            cluster_id = client_data.get('pattern_cluster_id')

        if cluster_id not in self.cluster_mappings:
            # No mappings for this cluster, return original
            return client_data

        mappings = self.cluster_mappings[cluster_id]

        # Create mapped version
        mapped_data = {
            'client_id': client_data['client_id'],
            'client_name': client_data.get('client_name'),
            'country': client_data.get('country'),
            'product': client_data.get('product'),
            'file_info': client_data.get('file_info'),
            'original_data': client_data,  # Preserve original
            'canonical_data': {},
            'processing_metadata': {
                'mapped_at': datetime.now().isoformat(),
                'cluster_id': cluster_id,
                'mapping_version': '1.0'
            }
        }

        # Extract and map fields
        extracted_fields = self._extract_all_fields(client_data)

        for source_field, value in extracted_fields.items():
            if source_field in mappings:
                mapping_info = mappings[source_field]
                canonical_field = mapping_info['canonical_field']
                transformation = mapping_info.get('transformation')

                # Apply transformation if specified
                if transformation and transformation in self.transformation_rules:
                    try:
                        value = self.transformation_rules[transformation](value)
                    except Exception as e:
                        mapped_data['processing_metadata'].setdefault('warnings', []).append(
                            f"Failed to transform {source_field}: {e}"
                        )

                # Validate against schema if defined
                if canonical_field in self.canonical_schema:
                    is_valid, error = self._validate_value(canonical_field, value)
                    if not is_valid:
                        mapped_data['processing_metadata'].setdefault('validation_errors', []).append(
                            f"{canonical_field}: {error}"
                        )

                mapped_data['canonical_data'][canonical_field] = value

        # Check for required fields
        self._check_required_fields(mapped_data)

        return mapped_data

    def _extract_all_fields(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all key-value fields from client data.

        Returns:
            Dictionary of field_name -> value
        """
        fields = {}

        for sheet in client_data.get('sheets', []):
            for section in sheet.get('sections', []):
                section_type = section.get('section_type')

                if section_type == 'key_value':
                    # Key-value sections map directly
                    fields.update(section.get('data', {}))

                # Note: Tables are not flattened here, they remain structured

        return fields

    def _validate_value(self, canonical_field: str, value: Any) -> tuple:
        """
        Validate value against canonical schema.

        Returns:
            (is_valid, error_message)
        """
        schema = self.canonical_schema.get(canonical_field)
        if not schema:
            return True, None

        field_type = schema['type']

        # Type validation
        if field_type == 'string' and not isinstance(value, str):
            if value is None:
                return True, None
            return False, f"Expected string, got {type(value).__name__}"

        elif field_type == 'number' and not isinstance(value, (int, float)):
            if value is None:
                return True, None
            return False, f"Expected number, got {type(value).__name__}"

        elif field_type == 'date':
            # Check if it's a date string
            if isinstance(value, str):
                # Basic date format check
                if not re.match(r'\d{4}-\d{2}-\d{2}', value):
                    return False, "Invalid date format (expected YYYY-MM-DD)"

        elif field_type == 'boolean' and not isinstance(value, bool):
            if value is None:
                return True, None
            return False, f"Expected boolean, got {type(value).__name__}"

        # Custom validation rules
        for rule in schema.get('validation_rules', []):
            is_valid, error = self._apply_validation_rule(rule, value)
            if not is_valid:
                return False, error

        return True, None

    def _apply_validation_rule(self, rule: str, value: Any) -> tuple:
        """
        Apply a validation rule.

        Supported rules:
        - "not_empty": Value must not be empty
        - "min_length:N": String must have at least N characters
        - "max_length:N": String must have at most N characters
        - "pattern:REGEX": Value must match regex pattern

        Returns:
            (is_valid, error_message)
        """
        if rule == "not_empty":
            if not value or (isinstance(value, str) and not value.strip()):
                return False, "Value cannot be empty"

        elif rule.startswith("min_length:"):
            min_len = int(rule.split(':')[1])
            if isinstance(value, str) and len(value) < min_len:
                return False, f"Minimum length is {min_len}"

        elif rule.startswith("max_length:"):
            max_len = int(rule.split(':')[1])
            if isinstance(value, str) and len(value) > max_len:
                return False, f"Maximum length is {max_len}"

        elif rule.startswith("pattern:"):
            pattern = rule.split(':', 1)[1]
            if isinstance(value, str) and not re.match(pattern, value):
                return False, f"Value must match pattern {pattern}"

        return True, None

    def _check_required_fields(self, mapped_data: Dict[str, Any]):
        """
        Check if required fields are present.

        Adds validation errors to mapped_data if fields are missing.
        """
        canonical_data = mapped_data['canonical_data']

        for field_name, schema in self.canonical_schema.items():
            if schema.get('required', False):
                if field_name not in canonical_data or canonical_data[field_name] is None:
                    mapped_data['processing_metadata'].setdefault('validation_errors', []).append(
                        f"Required field missing: {field_name}"
                    )

    def load_mappings(self, file_path: str):
        """
        Load mappings from JSON file.

        Args:
            file_path: Path to mappings file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.cluster_mappings = data.get('cluster_mappings', {})
        self.canonical_schema = data.get('canonical_schema', {})

        # Note: transformation_rules are not serializable, must be re-registered

    def save_mappings(self, file_path: str):
        """
        Save mappings to JSON file.

        Args:
            file_path: Path to output file
        """
        data = {
            'version': '1.0',
            'cluster_mappings': self.cluster_mappings,
            'canonical_schema': self.canonical_schema,
            'saved_at': datetime.now().isoformat()
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def export_mapping_template(self, cluster_id: int, output_path: str):
        """
        Export a template for manual field mapping.

        Args:
            cluster_id: Cluster ID to generate template for
            output_path: Output file path
        """
        # This would be populated by analyzing the cluster first
        template = {
            'cluster_id': cluster_id,
            'mappings': [
                {
                    'source_field': 'example_field',
                    'canonical_field': 'Example_Field',
                    'transformation': None,
                    'notes': 'Fill in your mappings here'
                }
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)


# Built-in transformation functions
def transform_uppercase(value: Any) -> str:
    """Convert value to uppercase string."""
    return str(value).upper() if value else None


def transform_lowercase(value: Any) -> str:
    """Convert value to lowercase string."""
    return str(value).lower() if value else None


def transform_trim(value: Any) -> str:
    """Trim whitespace from string."""
    return str(value).strip() if value else None


def transform_date_iso(value: Any) -> str:
    """
    Convert date to ISO format (YYYY-MM-DD).
    Handles multiple input formats.
    """
    if not value:
        return None

    if isinstance(value, str):
        # Already in ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}', value):
            return value[:10]

        # Try parsing other formats
        # Add your date parsing logic here
        return value

    return str(value)


def transform_boolean(value: Any) -> bool:
    """
    Convert value to boolean.
    Handles: Yes/No, Y/N, True/False, 1/0
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ['yes', 'y', 'true', '1']:
            return True
        elif value_lower in ['no', 'n', 'false', '0']:
            return False

    return None


def register_default_transformations(mapper: FieldMapper):
    """Register default transformation functions."""
    mapper.add_transformation_rule('uppercase', transform_uppercase)
    mapper.add_transformation_rule('lowercase', transform_lowercase)
    mapper.add_transformation_rule('trim', transform_trim)
    mapper.add_transformation_rule('date_iso', transform_date_iso)
    mapper.add_transformation_rule('boolean', transform_boolean)


# Example usage
if __name__ == '__main__':
    # Create mapper
    mapper = FieldMapper()

    # Register default transformations
    register_default_transformations(mapper)

    # Define canonical schema
    mapper.define_canonical_field(
        'Client_Name',
        'string',
        'Client legal name',
        required=True,
        validation_rules=['not_empty']
    )

    mapper.define_canonical_field(
        'Registration_ID',
        'string',
        'Client registration/license number',
        required=True,
        validation_rules=['not_empty']
    )

    mapper.define_canonical_field(
        'Country',
        'string',
        'Country of registration',
        required=True
    )

    # Add field mappings for cluster 0
    mapper.add_field_mapping(0, 'Client_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Customer_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Entity_Name', 'Client_Name', 'trim')

    mapper.add_field_mapping(0, 'Registration_ID', 'Registration_ID')
    mapper.add_field_mapping(0, 'Registration_Number', 'Registration_ID')
    mapper.add_field_mapping(0, 'License_Number', 'Registration_ID')

    # Save mappings
    mapper.save_mappings('field_mappings.json')

    print("Field mappings created and saved!")
