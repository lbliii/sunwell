# Frontend Testing Guide

## Overview

Sunwell Studio uses **Vitest** + **Testing Library** for component and store testing. This setup catches bugs like sparse arrays, undefined access, and state management issues before they reach production.

## Quick Start

```bash
# Install dependencies (includes test deps)
npm install

# Run tests
npm test

# Watch mode (re-run on changes)
npm run test:watch

# UI mode (visual test runner)
npm run test:ui

# Coverage report
npm run test:coverage
```

## Testing Strategy

### 1. **Component Tests** (`*.test.ts`)

Test Svelte components in isolation:

```typescript
import { render } from '@testing-library/svelte';
import MyComponent from './MyComponent.svelte';

it('renders correctly', () => {
  const { getByText } = render(MyComponent, { prop: 'value' });
  expect(getByText('value')).toBeInTheDocument();
});
```

**What to test:**
- ✅ Rendering with different props
- ✅ Edge cases (empty arrays, null values, sparse arrays)
- ✅ User interactions (clicks, inputs)
- ✅ Conditional rendering
- ✅ Error states

### 2. **Store Tests** (`*.test.ts`)

Test state management logic:

```typescript
import { get } from 'svelte/store';
import { myStore } from './myStore';

it('updates state correctly', () => {
  myStore.update(s => ({ ...s, value: 'new' }));
  expect(get(myStore).value).toBe('new');
});
```

**What to test:**
- ✅ State updates
- ✅ Derived state calculations
- ✅ Edge cases (empty/null inputs)
- ✅ Array operations (no sparse arrays!)
- ✅ Event handling

### 3. **Integration Tests** (Future)

For complex workflows, test multiple components together:

```typescript
import { render } from '@testing-library/svelte';
import { agentState } from '../stores/agent';
import ProjectView from '../routes/Project.svelte';

it('shows planning panel when planning', () => {
  agentState.update(s => ({ ...s, status: 'planning' }));
  const { getByText } = render(ProjectView);
  expect(getByText('Planning Details')).toBeInTheDocument();
});
```

## Common Patterns

### Testing Sparse Array Handling

```typescript
import { createSparseArray } from '../test/utils';

it('filters undefined entries', () => {
  const sparse = createSparseArray(5, { 0: item1, 4: item2 });
  const { getByText } = render(Component, { items: sparse });
  // Should only show 2 items, not 5
  expect(getByText('2 items')).toBeInTheDocument();
});
```

### Testing Store Events

```typescript
it('handles out-of-order events', () => {
  // Simulate events arriving in wrong order
  handleEvent({ type: 'item_2', data: {} });
  handleEvent({ type: 'item_0', data: {} });
  
  const state = get(myStore);
  expect(state.items).toHaveLength(2);
  expect(state.items.every(i => i != null)).toBe(true);
});
```

### Mocking Tauri API

Tauri APIs are automatically mocked in `src/test/setup.ts`. To customize:

```typescript
import { vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';

vi.mocked(invoke).mockResolvedValue({ data: 'test' });
```

## Test Organization

```
src/
├── components/
│   ├── MyComponent.svelte
│   └── MyComponent.test.ts      # Component tests
├── stores/
│   ├── myStore.ts
│   └── myStore.test.ts          # Store tests
└── test/
    ├── setup.ts                 # Global test setup
    └── utils.ts                 # Test utilities
```

## Coverage Goals

- **Components**: 80%+ coverage for complex components
- **Stores**: 90%+ coverage (critical business logic)
- **Utilities**: 100% coverage (pure functions)

## Best Practices

1. **Test behavior, not implementation** - Test what users see, not internal state
2. **Test edge cases** - Empty arrays, null values, sparse arrays, out-of-order events
3. **Keep tests fast** - Use mocks for slow operations (Tauri IPC, network)
4. **Write tests first** - For bug fixes, write a failing test, then fix
5. **Test in isolation** - Each test should be independent

## Examples

See these files for reference:
- `src/components/planning/CandidateComparison.test.ts` - Component testing
- `src/stores/agent.test.ts` - Store testing with sparse array handling

## Debugging Tests

```bash
# Run specific test file
npm test CandidateComparison

# Run tests matching pattern
npm test -- -t "sparse array"

# Debug mode (Node inspector)
npm test -- --inspect-brk
```

## CI Integration

Tests run automatically in CI. To run locally:

```bash
# Single run (like CI)
npm test -- --run
```

## Future Improvements

- [ ] E2E tests with Playwright (for full Tauri app testing)
- [ ] Visual regression testing
- [ ] Performance testing (render time, memory leaks)
- [ ] Accessibility testing (a11y)
