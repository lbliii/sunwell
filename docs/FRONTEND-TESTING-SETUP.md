# Frontend Testing Setup

## Why Frontend Tests?

The sparse array bug we just fixed (`TypeError: undefined is not an object`) is a perfect example of why frontend tests are essential:

1. **Caught bugs early** - Tests would have caught the sparse array issue before it reached users
2. **Prevent regressions** - Ensures fixes stay fixed
3. **Document behavior** - Tests serve as living documentation
4. **Enable refactoring** - Confidence to improve code without breaking things

## What We've Set Up

### Testing Stack

- **Vitest** - Fast, Vite-native test runner
- **Testing Library** - Component testing utilities
- **jsdom** - DOM simulation for Node.js testing
- **Coverage** - Built-in coverage reporting

### Test Structure

```
studio/
├── vitest.config.ts              # Test configuration
├── src/
│   ├── test/
│   │   ├── setup.ts              # Global test setup (mocks, cleanup)
│   │   └── utils.ts             # Test utilities
│   ├── components/
│   │   └── planning/
│   │       ├── CandidateComparison.svelte
│   │       └── CandidateComparison.test.ts  # Component tests
│   └── stores/
│       ├── agent.ts
│       └── agent.test.ts         # Store tests
└── TESTING.md                    # Testing guide
```

## Example: The Bug We Fixed

### Before (No Tests)

```typescript
// agent.ts - Creates sparse array
candidates[candidateIndex] = { ... };

// CandidateComparison.svelte - Crashes on undefined
{#each candidates as candidate}
  {candidate.index}  // 💥 TypeError if candidate is undefined
{/each}
```

### After (With Tests)

```typescript
// agent.test.ts - Catches the bug
it('creates dense array without undefined entries', () => {
  handleAgentEvent({ type: 'plan_candidate_generated', data: { candidate_index: 5 } });
  const state = get(agentState);
  expect(state.planningCandidates).toHaveLength(1);
  expect(state.planningCandidates.every(c => c != null)).toBe(true);
});

// CandidateComparison.test.ts - Verifies fix
it('filters out undefined entries from sparse arrays', () => {
  const sparse = createSparseArray(6, { 0: item1, 5: item2 });
  render(CandidateComparison, { candidates: sparse });
  // Should only show 2 items, not crash
});
```

## Getting Started

### 1. Install Dependencies

```bash
cd studio
npm install
```

This installs:
- `vitest` - Test runner
- `@testing-library/svelte` - Component testing
- `@testing-library/jest-dom` - DOM matchers
- `jsdom` - DOM environment
- `@vitest/ui` - Visual test runner

### 2. Run Tests

```bash
# Run all tests
npm test

# Watch mode (re-run on changes)
npm run test:watch

# UI mode (visual test runner)
npm run test:ui

# Coverage report
npm run test:coverage
```

### 3. Write Your First Test

Create `src/components/MyComponent.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import MyComponent from './MyComponent.svelte';

describe('MyComponent', () => {
  it('renders correctly', () => {
    const { getByText } = render(MyComponent, { prop: 'value' });
    expect(getByText('value')).toBeInTheDocument();
  });
});
```

## Testing Strategy

### Priority 1: Critical Paths (Do First)

1. **Store logic** - State management, event handling
2. **Array operations** - Sparse arrays, filtering, mapping
3. **Edge cases** - Empty/null/undefined handling
4. **User interactions** - Clicks, inputs, navigation

### Priority 2: Components (Do Next)

1. **Complex components** - Multi-step flows, conditional rendering
2. **Form components** - Input validation, submission
3. **List components** - Rendering arrays, filtering

### Priority 3: Integration (Do Later)

1. **Component interactions** - Multiple components working together
2. **Store + Component** - Components using stores
3. **E2E flows** - Complete user workflows

## Coverage Goals

- **Stores**: 90%+ (critical business logic)
- **Components**: 80%+ (complex components)
- **Utilities**: 100% (pure functions)

Current coverage: **0%** → Target: **70%+** in next sprint

## Common Test Patterns

### Testing Sparse Arrays

```typescript
import { createSparseArray } from '../test/utils';

it('handles sparse arrays', () => {
  const sparse = createSparseArray(5, { 0: item1, 4: item2 });
  const { getByText } = render(Component, { items: sparse });
  expect(getByText('2 items')).toBeInTheDocument();
});
```

### Testing Store Updates

```typescript
import { get } from 'svelte/store';
import { myStore, handleEvent } from './myStore';

it('updates state correctly', () => {
  handleEvent({ type: 'update', data: { value: 'new' } });
  expect(get(myStore).value).toBe('new');
});
```

### Testing Edge Cases

```typescript
it('handles empty array', () => {
  const { container } = render(Component, { items: [] });
  expect(container.querySelector('.empty-state')).toBeInTheDocument();
});

it('handles null values', () => {
  const { container } = render(Component, { value: null });
  expect(container.querySelector('.placeholder')).toBeInTheDocument();
});
```

## Next Steps

1. ✅ **Setup complete** - Vitest configured, example tests written
2. 🔄 **Add more tests** - Start with stores, then components
3. 🔄 **CI integration** - Run tests on every PR
4. 🔄 **Coverage tracking** - Set up coverage reporting
5. 🔄 **E2E tests** - Add Playwright for full app testing

## Resources

- [Vitest Docs](https://vitest.dev/)
- [Testing Library Svelte](https://testing-library.com/docs/svelte-testing-library/intro/)
- [TESTING.md](../studio/TESTING.md) - Detailed testing guide

## Questions?

- See `studio/TESTING.md` for detailed examples
- Check `studio/src/components/planning/CandidateComparison.test.ts` for component test examples
- Check `studio/src/stores/agent.test.ts` for store test examples
