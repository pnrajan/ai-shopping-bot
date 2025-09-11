# Inflection Curator - Package Structure

This document describes the reorganized package structure for the Inflection Curator project.

## 📦 Package Structure

```
inflection_curator/                    # Main package
├── __init__.py                       # Package entry point with public API
├── core/                             # Core orchestration logic
│   ├── __init__.py
│   ├── exceptions.py                 # Custom exception classes
│   └── orchestrator.py              # Main ShoppingOrchestrator
├── personas/                         # Persona system
│   ├── __init__.py
│   ├── base.py                      # Abstract base persona class
│   ├── shopping.py                  # Shopping-specific persona implementation
│   └── configs/                     # Persona configuration files
│       └── shopping_configs/
│           ├── default.yaml
│           ├── budget_hunter.yaml
│           └── expert.yaml
├── planning/                         # Planning and execution pipeline
│   ├── __init__.py
│   ├── query_parser.py              # Shopping query parser
│   ├── planner.py                   # Shopping execution planner
│   ├── executor.py                  # Shopping task executor
│   └── registry.py                  # Tool registry and validation
├── providers/                        # External service providers
│   ├── __init__.py
│   ├── product_providers.py         # UnWrangle and other providers
│   └── provider_response.py         # Provider response models
├── classifiers/                      # Intent classification
│   ├── __init__.py
│   ├── intent_classifier.py         # Intent classification logic
│   └── query_undertanding.py        # Query understanding components
├── tools/                            # Tool implementations (future expansion)
│   └── __init__.py
├── utils/                            # Utility functions
│   ├── __init__.py
│   ├── config.py                    # Configuration management
│   └── logger.py                    # Logging utilities
├── constants.py                      # Project constants
└── settings.py                       # Application settings
```

## 🔧 Key Components

### 1. Core Module (`core/`)
- **`orchestrator.py`**: Main orchestration logic with planning pipeline
- **`exceptions.py`**: Custom exception classes for better error handling

### 2. Personas Module (`personas/`)
- **`base.py`**: Abstract base class for all personas
- **`shopping.py`**: Complete shopping persona with tools and logic
- **`configs/`**: YAML configuration files for different persona variants

### 3. Planning Module (`planning/`)
- **`query_parser.py`**: Converts natural language to structured attributes
- **`planner.py`**: Generates execution plans from parsed attributes
- **`executor.py`**: Executes plans using appropriate tools
- **`registry.py`**: Tool validation and registry management

### 4. Providers Module (`providers/`)
- **`product_providers.py`**: External API integrations (UnWrangle, etc.)
- **`provider_response.py`**: Pydantic models for provider responses

## 🚀 Usage

### Basic Usage
```python
from inflection_curator import ShoppingOrchestrator, ShoppingMode

# Initialize the orchestrator
orch = ShoppingOrchestrator()

# Handle a shopping request
result = orch.handle("I need wireless headphones under $100")
print(result)

# Switch personas
orch.set_persona("budget_hunter")

# Change execution mode
orch.set_mode(ShoppingMode.AGENT_ONLY)
```

### Advanced Usage
```python
from inflection_curator.personas import ShoppingPersona
from inflection_curator.planning import ShoppingQueryParser

# Direct component usage
parser = ShoppingQueryParser()
attributes = parser.parse("gaming laptop under $1500")

# Custom persona configuration
persona = ShoppingPersona.from_config("custom_config.yaml")
```

## 🔄 Planning Flow

The system follows this execution pattern:

1. **Orchestrator** receives user input
2. **Query Parser** converts natural language to structured attributes
3. **Planner** generates execution plan from attributes
4. **Tool Registry** validates the planned tools and arguments
5. **Executor** runs the validated plan using shopping tools

## 📊 Architecture Benefits

### 1. **Domain Specificity**
- All components are clearly labeled as shopping-focused
- Shopping-specific optimizations throughout the pipeline

### 2. **Modular Design**
- Clear separation of concerns
- Easy to extend with new personas or tools
- Independent testing of components

### 3. **Scalability**
- Well-organized package structure
- Easy to add new modules (e.g., `travel/`, `finance/`)
- Clean import paths

### 4. **Maintainability**
- Proper package hierarchy
- Consistent naming conventions
- Clear dependencies between modules

### 5. **Professional Standards**
- Matches Python packaging best practices
- Compatible with `pyproject.toml` configuration
- Ready for distribution and installation

## 🏗️ Migration from Legacy

The reorganization preserves all existing functionality while providing:

- **Better Organization**: Logical grouping of related components
- **Clear Interfaces**: Well-defined public APIs
- **Type Safety**: Proper exception handling and validation
- **Documentation**: Self-documenting structure and naming

## 🎯 Future Expansion

The structure is designed to easily accommodate:

- **New Personas**: Add to `personas/` with their own configs
- **Additional Tools**: Expand `tools/` module with domain-specific tools
- **New Providers**: Add provider integrations to `providers/`
- **Enhanced Planning**: Extend planning capabilities in `planning/`

This architecture provides a solid foundation for building a comprehensive AI assistant system while maintaining focus on the shopping domain.
