---
name: frontend-standards
description: React/Next.js frontend standards — component composition, compound components, custom hooks, Context+Reducer state, memoization, code splitting, list virtualization, forms, error boundaries, Framer Motion animation and accessible keyboard/focus patterns. Use when writing, reviewing or refactoring React or Next.js components, hooks or client-side state.
---

# Frontend Standards — React / Next.js

Client-side conventions the generated code must satisfy. UI/UX rules (accessibility, touch
targets, contrast, animation timing) live in the `ui-standards` skill.

Business logic does not live here: it lives in the framework-free core layer the DOE gate
measures. Components and hooks are the thin layer on top. See `.doe/README.md`.

---

## Component Patterns

**Composition over inheritance.** Build small parts, assemble at the call site.

```typescript
export function Card({ children, variant = 'default' }: CardProps) {
  return <div className={`card card-${variant}`}>{children}</div>;
}
export const CardHeader = ({ children }: PropsWithChildren) => <div className="card-header">{children}</div>;
export const CardBody = ({ children }: PropsWithChildren) => <div className="card-body">{children}</div>;
```

**Compound components** when children need shared state — expose it via context, throw if used
outside the provider.

```typescript
const TabsContext = createContext<TabsContextValue | undefined>(undefined);

export function Tab({ id, children }: TabProps) {
  const context = useContext(TabsContext);
  if (!context) throw new Error('Tab must be used within Tabs');

  return (
    <button className={context.activeTab === id ? 'active' : ''}
            onClick={() => context.setActiveTab(id)}>
      {children}
    </button>
  );
}
```

**Render props** when the consumer must control rendering of async state (data / loading / error).

---

## Custom Hooks

Extract reusable logic. One concern per hook.

```typescript
export function useToggle(initialValue = false): [boolean, () => void] {
  const [value, setValue] = useState(initialValue);
  const toggle = useCallback(() => setValue(v => !v), []);
  return [value, toggle];
}

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debounced;
}
```

Common set: `useToggle`, `useDebounce`, `useQuery`. Reach for TanStack Query before writing your
own fetch/cache hook — library-first.

---

## State Management

| Scope | Use |
|---|---|
| Component-level | `useState` |
| Complex shared state | Context + Reducer |
| Global app state | Zustand / Redux — don't reinvent |

```typescript
type Action =
  | { type: 'SET_MARKETS'; payload: Market[] }
  | { type: 'SELECT_MARKET'; payload: Market };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_MARKETS':   return { ...state, markets: action.payload };
    case 'SELECT_MARKET': return { ...state, selectedMarket: action.payload };
    default:              return state;
  }
}

export function useMarkets() {
  const context = useContext(MarketContext);
  if (!context) throw new Error('useMarkets must be used within MarketProvider');
  return context;
}
```

---

## Performance

```typescript
// useMemo — expensive computations only
const sortedMarkets = useMemo(() => [...markets].sort((a, b) => b.volume - a.volume), [markets]);

// useCallback — functions passed as props
const handleSearch = useCallback((query: string) => setSearchQuery(query), []);

// React.memo — pure presentational components
export const MarketCard = React.memo<MarketCardProps>(({ market }) => ( /* … */ ));
```

**Code splitting** — lazy load heavy components behind `Suspense` with a real skeleton fallback.

```typescript
const HeavyChart = lazy(() => import('./HeavyChart'));

<Suspense fallback={<ChartSkeleton />}>
  <HeavyChart data={data} />
</Suspense>
```

**Virtualize long lists** (`@tanstack/react-virtual`) — never render thousands of rows.

⚠️ Note: `.sort()` mutates. Spread before sorting inside `useMemo` or you mutate props.

---

## Forms

- Validate on submit, show errors near the offending field
- Disable the submit button during async operations
- Keep `formData` and `errors` as separate state
- In React artifacts: never use `<form>` tags — wire `onClick` / `onChange` directly

---

## Error Boundaries

```typescript
export class ErrorBoundary extends React.Component<PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    Sentry.captureException(error, { extra: errorInfo });
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return <ErrorFallback error={this.state.error} onRetry={() => this.setState({ hasError: false })} />;
  }
}
```

Wrap route-level boundaries at minimum. Report to Sentry, not `console.error`.

---

## Animation (Framer Motion)

```typescript
<AnimatePresence>
  {markets.map(market => (
    <motion.div key={market.id}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}>
      <MarketCard market={market} />
    </motion.div>
  ))}
</AnimatePresence>
```

Stable `key` per item or exit animations break. Timing rules → `ui-standards`.

---

## Accessibility in Components

**Keyboard navigation** — handle `ArrowUp` / `ArrowDown` / `Enter` / `Escape` on any custom
dropdown, listbox or menu. `preventDefault()` on arrows so the page doesn't scroll.

**Focus management** — on modal open, save `document.activeElement`, focus the modal, restore focus
on close. Set `role="dialog"` + `aria-modal="true"` + `tabIndex={-1}`.

---

## Code Review

### Comment format
```
🔴 BLOCKING: SQL injection vulnerability
🟡 SUGGESTION: Consider useMemo for performance
🟢 NIT: Prefer const over let
❓ QUESTION: What happens if user is null?
```

### Checklist
- [ ] Edge cases + error states handled (empty, loading, error)
- [ ] No unnecessary re-renders · [ ] Bundle size impact considered
- [ ] Clear naming, no magic numbers · [ ] DRY, SOLID
- [ ] TypeScript types — never `any`
