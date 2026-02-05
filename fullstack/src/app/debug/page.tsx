import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const dynamic = 'force-dynamic';

const dashboards = [
  {
    name: 'Redpanda Console',
    description: 'Kafka topic browser, message production/consumption, schema registry',
    url: 'http://localhost:8080',
    icon: '📊',
    color: 'bg-red-500',
    features: ['Topics', 'Messages', 'Schemas', 'Consumers'],
  },
  {
    name: 'Temporal Web UI',
    description: 'Workflow monitoring, execution history, workers status',
    url: 'http://localhost:8088',
    icon: '⚡',
    color: 'bg-purple-500',
    features: ['Workflows', 'History', 'Workers', 'Namespaces'],
  },
  {
    name: 'Jaeger Tracing',
    description: 'Distributed trace visualization, service dependencies',
    url: 'http://localhost:16686',
    icon: '🔍',
    color: 'bg-amber-500',
    features: ['Traces', 'Spans', 'Services', 'Latency'],
  },
  {
    name: 'pgAdmin',
    description: 'PostgreSQL database management, query tool, schema browser',
    url: 'http://localhost:5050',
    icon: '🐘',
    color: 'bg-blue-500',
    features: ['Query Tool', 'Schemas', 'Tables', 'Users'],
    note: 'Email: admin@localhost | Password: admin',
  },
  {
    name: 'Prisma Studio',
    description: 'Database GUI for IterateSwarm data (Feedback, Issues)',
    url: 'http://localhost:5555',
    icon: '🗄️',
    color: 'bg-teal-500',
    features: ['Feedback', 'Issues', 'Audit Logs', 'Relations'],
  },
  {
    name: 'NetData',
    description: 'Real-time infrastructure monitoring (CPU, Memory, Disk, Network)',
    url: 'http://localhost:19999',
    icon: '📈',
    color: 'bg-green-500',
    features: ['CPU', 'Memory', 'Disk', 'Network'],
  },
];

export default function DebugPage() {
  return (
    <div className="min-h-screen bg-stone-50 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-stone-900">IterateSwarm Dashboard</h1>
          <p className="text-stone-600 mt-1">
            Central access to all service dashboards and monitoring tools
          </p>
        </div>

        {/* Service Dashboards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {dashboards.map((dashboard) => (
            <Link
              key={dashboard.name}
              href={dashboard.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group"
            >
              <Card className="h-full hover:shadow-lg transition-all duration-200 border-2 hover:border-stone-400">
                <CardHeader className="flex flex-row items-center gap-4 pb-2">
                  <div className={`w-12 h-12 rounded-lg ${dashboard.color} flex items-center justify-center text-2xl`}>
                    {dashboard.icon}
                  </div>
                  <div>
                    <CardTitle className="text-lg group-hover:text-blue-600 transition-colors">
                      {dashboard.name}
                    </CardTitle>
                    <Badge variant="secondary" className="mt-1 text-xs">
                      External
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-stone-600 mb-4">
                    {dashboard.description}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {dashboard.features.map((feature) => (
                      <Badge key={feature} variant="outline" className="text-xs">
                        {feature}
                      </Badge>
                    ))}
                  </div>
                  {dashboard.note && (
                    <p className="text-xs text-stone-500 mt-2">{dashboard.note}</p>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Quick Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <a
                href="http://localhost:8080/topics/feedback-events"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">📨</span>
                <div>
                  <p className="font-medium">View Feedback Topic</p>
                  <p className="text-sm text-stone-500">See Kafka messages</p>
                </div>
              </a>
              <a
                href="http://localhost:8088/namespaces/default/workflows"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">⚡</span>
                <div>
                  <p className="font-medium">Workflow Executions</p>
                  <p className="text-sm text-stone-500">Monitor AI processing</p>
                </div>
              </a>
              <a
                href="http://localhost:16686/search?service=iterateswarm"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">🔍</span>
                <div>
                  <p className="font-medium">Search Traces</p>
                  <p className="text-sm text-stone-500">Debug distributed calls</p>
                </div>
              </a>
              <a
                href="http://localhost:5050/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">🔎</span>
                <div>
                  <p className="font-medium">Query Database</p>
                  <p className="text-stone-500">SQL queries</p>
                </div>
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Architecture Diagram */}
        <Card>
          <CardHeader>
            <CardTitle>System Architecture</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-stone-900 text-stone-100 p-4 rounded-lg overflow-x-auto text-sm">
{`┌─────────────────────────────────────────────────────────────────────┐
│                      IterateSwarm Architecture                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│  │  Discord    │     │   Slack    │     │   GitHub    │          │
│  │  Webhooks   │────▶│  Webhooks   │────▶│  Webhooks   │          │
│  └─────────────┘     └─────────────┘     └─────────────┘          │
│         │                   │                   │                  │
│         └───────────────────┴───────────────────┘                  │
│                           │                                          │
│                    ┌──────▼──────┐                                  │
│                    │  Go Server  │  (localhost:3000)               │
│                    │  /webhooks  │                                  │
│                    └──────┬──────┘                                  │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                        │
│         ▼                 ▼                 ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Redpanda   │  │  Temporal   │  │  PostgreSQL │              │
│  │ (Kafka)     │  │  Workflow   │  │  Database   │              │
│  │ :9092/8080  │  │  :7233/8088 │  │  :5432/5050 │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                           │                                          │
│                    ┌──────▼──────┐                                  │
│                    │  Python AI  │  (LangGraph Agents)              │
│                    │  Ollama     │  (localhost:11434)              │
│                    └──────┬──────┘                                  │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                        │
│         ▼                 ▼                 ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Qdrant     │  │  Jaeger     │  │  GitHub     │              │
│  │  Vector DB  │  │  Tracing    │  │  API        │              │
│  │  :6333      │  │  :16686     │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘`}
            </pre>
          </CardContent>
        </Card>

        {/* Service Status */}
        <Card>
          <CardHeader>
            <CardTitle>Service Ports Reference</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div className="flex items-center justify-between p-3 bg-stone-100 rounded">
                <span className="font-mono">localhost:3000</span>
                <span>Go API Server</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-stone-100 rounded">
                <span className="font-mono">localhost:3001</span>
                <span>Next.js Frontend</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-stone-100 rounded">
                <span className="font-mono">localhost:7233</span>
                <span>Temporal (gRPC)</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-red-100 rounded">
                <span className="font-mono">localhost:8080</span>
                <span>Redpanda Console</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-purple-100 rounded">
                <span className="font-mono">localhost:8088</span>
                <span>Temporal Web UI</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-amber-100 rounded">
                <span className="font-mono">localhost:9094</span>
                <span>Kafka (External)</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-blue-100 rounded">
                <span className="font-mono">localhost:5050</span>
                <span>pgAdmin</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-blue-100 rounded">
                <span className="font-mono">localhost:5432</span>
                <span>PostgreSQL</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-teal-100 rounded">
                <span className="font-mono">localhost:5555</span>
                <span>Prisma Studio</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-amber-100 rounded">
                <span className="font-mono">localhost:16686</span>
                <span>Jaeger UI</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-orange-100 rounded">
                <span className="font-mono">localhost:6333</span>
                <span>Qdrant (Vectors)</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-green-100 rounded">
                <span className="font-mono">localhost:19999</span>
                <span>NetData</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
