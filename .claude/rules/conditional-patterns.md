# Conditional Patterns

## Threshold

Refactor when a function has **4+ sequential if-conditions**. Aim for at most 2-3 conditions (guard clauses only) per function.

## Pattern 1: Guard Clauses (Early Returns)

**When:** Precondition checks, validation, nested if-else pyramids.

**Rule:** Check exceptional/invalid cases first and return immediately. Keep the happy path at the lowest indentation level.

```python
# Bad — nested pyramid
def process(self, data):
    if data:
        if data.is_valid:
            if self.can_process:
                return self._do_work(data)
    return None

# Good — guard clauses
def process(self, data):
    if not data or not data.is_valid:
        return None
    if not self.can_process:
        return None
    return self._do_work(data)
```

## Pattern 2: Dictionary Dispatch

**When:** Branching on a single value (enum, string key, command name).

**Rule:** Replace if/elif chains with a `dict[key, callable]` lookup. Each handler becomes a named, testable function.

```python
# Bad — if/elif chain
def handle(self, op_type, data):
    if op_type == "insert":
        self._insert(data)
    elif op_type == "update":
        self._update(data)
    elif op_type == "delete":
        self._delete(data)

# Good — dict dispatch
_HANDLERS = {
    "insert": _insert,
    "update": _update,
    "delete": _delete,
}

def handle(self, op_type, data):
    handler = self._HANDLERS.get(op_type)
    if handler:
        handler(self, data)
```

## Pattern 3: Null Object

**When:** Multiple `if x is not None` / `if not x` checks for the same optional dependency.

**Rule:** Provide a no-op implementation of the interface so callers can treat all objects uniformly without defensive `None` checks.

```python
# Bad — repeated None guards
if self._store:
    self._store.save(data)
if self._store:
    result = self._store.retrieve(query)

# Good — NullStore always exists
class NullStore(Store):
    def save(self, data): pass
    def retrieve(self, query): return []

# Caller code — no guards needed
self._store.save(data)
result = self._store.retrieve(query)
```
