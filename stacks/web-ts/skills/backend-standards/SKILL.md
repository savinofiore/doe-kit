---
name: backend-standards
description: Backend standards for Node.js/Express/TypeScript — layered architecture, BaseController, unifiedConfig, Sentry, Zod validation, repository pattern, REST API design, Prisma/Supabase query patterns, caching, rate limiting, job queues, structured logging. Use when writing, reviewing or refactoring server-side code, API routes, controllers, services, repositories or database access.
---

# Backend Standards — Node.js / Express / TypeScript

Server-side conventions the generated code must satisfy. The DOE gate checks that the code
works; this skill says what "works" is allowed to look like.

The first three sections are not style: layering, the repository pattern and injected clients
are what make a deterministic offline gate possible at all. See `.doe/README.md`.

---

## Architecture (Clean Architecture + DDD)

```
HTTP Request → Routes → Controllers → Services → Repositories → Database
```

Each layer has ONE responsibility.

```
service/src/
├── config/          # unifiedConfig
├── controllers/     # Request handlers (extend BaseController)
├── services/        # Business logic (DI)
├── repositories/    # Data access (Prisma)
├── routes/          # Routing only
├── middleware/      # Auth, validation, error handling
├── validators/      # Zod schemas
├── types/
├── tests/
├── instrument.ts    # Sentry — FIRST IMPORT
├── app.ts           # Express setup
└── server.ts        # HTTP server
```

**Naming:** Controllers `PascalCase` (`UserController.ts`) · Services `camelCase`
(`userService.ts`) · Routes `camelCase + Routes` (`userRoutes.ts`) · Repositories
`PascalCase + Repository` (`UserRepository.ts`).

### Anti-patterns
- Business logic in routes or controllers
- Database queries in controllers
- Generic naming: `utils.js` with 50 unrelated functions
- Custom auth when Auth0/Supabase exists
- Custom state management instead of Zustand/Redux
- `console.log` instead of Sentry

---

## 7 Key Rules

1. **Routes only route** — delegate everything to controller
2. **All controllers extend BaseController**
3. **All errors to Sentry** — `Sentry.captureException(error)`
4. **Use `unifiedConfig`, NEVER `process.env`**
5. **Validate all input with Zod**
6. **Use Repository pattern for data access**
7. **Tests required** — unit + integration

```typescript
// Controller
export class UserController extends BaseController {
  async getUser(req: Request, res: Response): Promise<void> {
    try {
      const user = await this.userService.findById(req.params.id);
      this.handleSuccess(res, user);
    } catch (error) {
      this.handleError(error, res, 'getUser');
    }
  }
}

// Zod validation
const schema = z.object({ email: z.string().email() });
const validated = schema.parse(req.body);

// Repository
const users = await userRepository.findActive();
```

### New feature checklist
- [ ] Route (delegates only) · [ ] Controller extends BaseController · [ ] Service with DI
- [ ] Repository (if complex) · [ ] Zod schema · [ ] Sentry capture · [ ] Unit + integration tests
- [ ] Config via `unifiedConfig`

---

## API Design

```
GET    /api/resources          # List
GET    /api/resources/:id      # Single
POST   /api/resources          # Create
PUT    /api/resources/:id      # Replace
PATCH  /api/resources/:id      # Update
DELETE /api/resources/:id      # Delete

GET /api/resources?status=active&sort=volume&limit=20&offset=0
```

- Nouns in URLs, not verbs (`/users` not `/getUsers`)
- Consistent response envelope
- Always rate limit public APIs
- Document with OpenAPI/Swagger
- Choose REST vs GraphQL vs tRPC per context — don't default to REST blindly
- Never expose internal errors to clients

**Status codes:** `200` Success · `201` Created · `400` Bad Request · `401` Unauthorized ·
`403` Forbidden · `404` Not Found · `429` Rate Limited · `500` Server Error

### Centralized error handler

```typescript
class ApiError extends Error {
  constructor(public statusCode: number, public message: string, public isOperational = true) {
    super(message);
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export function errorHandler(error: unknown) {
  if (error instanceof ApiError) {
    return json({ success: false, error: error.message }, { status: error.statusCode });
  }
  if (error instanceof z.ZodError) {
    return json({ success: false, error: 'Validation failed', details: error.errors }, { status: 400 });
  }
  Sentry.captureException(error);
  return json({ success: false, error: 'Internal server error' }, { status: 500 });
}
```

---

## Auth & Authorization

```typescript
export function verifyToken(token: string): JWTPayload {
  try {
    return jwt.verify(token, config.auth.jwtSecret) as JWTPayload;
  } catch {
    throw new ApiError(401, 'Invalid token');
  }
}

// RBAC
const rolePermissions: Record<Role, Permission[]> = {
  admin: ['read', 'write', 'delete', 'admin'],
  moderator: ['read', 'write', 'delete'],
  user: ['read', 'write'],
};

export const hasPermission = (user: User, permission: Permission): boolean =>
  rolePermissions[user.role].includes(permission);
```

---

## Database Patterns

```typescript
// ✅ Select only needed columns
const { data } = await supabase
  .from('markets')
  .select('id, name, status')
  .eq('status', 'active')
  .limit(10);

// ❌ .select('*')

// ✅ Batch fetch to avoid N+1
const creatorIds = markets.map(m => m.creator_id);
const creators = await getUsers(creatorIds);           // 1 query, not N
const creatorMap = new Map(creators.map(c => [c.id, c]));
markets.forEach(m => { m.creator = creatorMap.get(m.creator_id); });
```

**Transactions** — push multi-write operations into a DB function (Supabase RPC) or a Prisma
`$transaction`, never orchestrate partial writes from the service layer.

---

## Caching

Cache-aside is the default. Wrap the repository, don't scatter cache calls through services.

```typescript
async function getMarketWithCache(id: string): Promise<Market> {
  const cacheKey = `market:${id}`;
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  const market = await db.markets.findUnique({ where: { id } });
  if (!market) throw new ApiError(404, 'Market not found');

  await redis.setex(cacheKey, 300, JSON.stringify(market));
  return market;
}
```

Invalidate on write. TTL by volatility, not by habit.

---

## Resilience

```typescript
// Exponential backoff — prefer `cockatiel` over hand-rolling this
async function fetchWithRetry<T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> {
  let lastError: Error;
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (i < maxRetries - 1) await sleep(Math.pow(2, i) * 1000);
    }
  }
  throw lastError!;
}
```

**Rate limiting** — token bucket or sliding window, keyed on IP or user id. In-memory only for
single-instance services; Redis-backed otherwise.

**Background jobs** — queue anything slower than the request budget; return `202` + job id rather
than blocking the handler.

---

## Logging & Monitoring

Structured JSON only. One `requestId` threaded through the request lifecycle.

```typescript
logger.info('Fetching markets', { requestId, method: 'GET', path: '/api/markets' });
logger.error('Failed to fetch markets', error, { requestId });
```

Errors go to Sentry **and** the log — Sentry for alerting, logs for correlation.

---

## Async Patterns

```typescript
async function fetchData(id: string) {
  try {
    const response = await fetch(`/api/${id}`);
    if (!response.ok) throw new Error('Failed');
    return await response.json();
  } catch (error) {
    Sentry.captureException(error);
    throw error;
  }
}

// Parallel when independent
const [users, posts] = await Promise.all([fetchUsers(), fetchPosts()]);
```

---

## JavaScript Semantics

- `===` over `==` · `const` > `let` > `var`
- `??` checks only `null`/`undefined`; `||` catches all falsy values
- Microtasks (Promises) run before macrotasks (`setTimeout`)
- Arrow functions inherit `this` lexically
- `Object.is(NaN, NaN)` → `true`; `NaN === NaN` → `false`
- Closures capture variables by reference, not value

---

## Code Review

### Correctness
- [ ] Edge cases handled · [ ] Error handling in place · [ ] No obvious bugs

### Security
- [ ] Input validated and sanitized · [ ] No SQL/NoSQL injection · [ ] No XSS or CSRF
- [ ] No hardcoded secrets · [ ] AI outputs sanitized before use in critical sinks

### Performance
- [ ] No N+1 queries · [ ] Appropriate caching · [ ] Bundle size considered

### Quality
- [ ] Clear naming, no magic numbers · [ ] DRY, SOLID · [ ] TypeScript types — never `any`

### Comment format
```
🔴 BLOCKING: SQL injection vulnerability
🟡 SUGGESTION: Consider useMemo for performance
🟢 NIT: Prefer const over let
❓ QUESTION: What happens if user is null?
```
