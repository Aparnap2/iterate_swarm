import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const dynamic = 'force-dynamic';

const dashboards = [
  {
    name: 'Supabase Studio',
    description: 'Database, Auth, Storage, Realtime - all-in-one',
    url: 'http://localhost:3000',
    icon: '🔥',
    color: 'bg-orange-500',
    features: ['Database', 'Auth', 'Storage', 'Realtime'],
    note: 'Primary backend for IterateSwarm',
  },
  {
    name: 'NetData',
    description: 'Real-time infrastructure monitoring',
    url: 'http://localhost:19999',
    icon: '📈',
    color: 'bg-green-500',
    features: ['CPU', 'Memory', 'Disk', 'Network'],
    status: 'running',
  },
  {
    name: 'Ollama',
    description: 'Local LLM inference engine',
    url: 'http://localhost:11434',
    icon: '🧠',
    color: 'bg-purple-500',
    features: ['LLM Inference', 'Embeddings', 'Models'],
    status: 'docker',
  },
];

const localServices = [
  { port: '3001', name: 'Next.js Frontend', status: 'local' },
  { port: '3000', name: 'Supabase Studio', status: 'docker' },
  { port: '5432', name: 'PostgreSQL (Supabase)', status: 'docker' },
  { port: '6333', name: 'Qdrant Vector DB', status: 'docker' },
  { port: '11434', name: 'Ollama LLM', status: 'docker' },
  { port: '19999', name: 'NetData Monitoring', status: 'running' },
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
                      {dashboard.status || 'External'}
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

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <a
                href="http://localhost:3000"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">🔥</span>
                <div>
                  <p className="font-medium">Supabase Studio</p>
                  <p className="text-sm text-stone-500">Database & Auth</p>
                </div>
              </a>
              <a
                href="http://localhost:11434"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">🧠</span>
                <div>
                  <p className="font-medium">Ollama</p>
                  <p className="text-sm text-stone-500">LLM Models</p>
                </div>
              </a>
              <a
                href="http://localhost:19999"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">📈</span>
                <div>
                  <p className="font-medium">NetData</p>
                  <p className="text-sm text-stone-500">Monitoring</p>
                </div>
              </a>
              <a
                href="http://localhost:3001"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 rounded-lg border hover:bg-stone-50 transition-colors"
              >
                <span className="text-2xl">⚡</span>
                <div>
                  <p className="font-medium">IterateSwarm</p>
                  <p className="text-sm text-stone-500">Next.js App</p>
                </div>
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Service Ports Reference */}
        <Card>
          <CardHeader>
            <CardTitle>Service Ports Reference</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              {localServices.map((service) => (
                <div
                  key={service.port}
                  className={`flex items-center justify-between p-3 rounded ${
                    service.status === 'running'
                      ? 'bg-green-100'
                      : service.status === 'docker'
                      ? 'bg-blue-100'
                      : 'bg-stone-100'
                  }`}
                >
                  <span className="font-mono">{service.port}</span>
                  <span>{service.name}</span>
                </div>
              ))}
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
│                    │  Next.js    │  (localhost:3001)                 │
│                    │  Frontend   │                                  │
│                    └──────┬──────┘                                  │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                        │
│         ▼                 ▼                 ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Supabase   │  │   Ollama    │  │  Qdrant     │              │
│  │  (Postgres) │  │  LLM        │  │  Vector DB  │              │
│  │  :5432      │  │  :11434     │  │  :6333      │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                           │                                          │
│                    ┌──────▼──────┐                                  │
│                    │  NetData    │  (localhost:19999)               │
│                    │  Monitoring │                                  │
│                    └─────────────┘                                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘`}
            </pre>
          </CardContent>
        </Card>

        {/* Authentication */}
        <Card>
          <CardHeader>
            <CardTitle>Authentication</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-blue-100 text-blue-800">Better Auth</Badge>
                </div>
                <p className="text-sm text-blue-700">
                  Email/password and GitHub OAuth authentication configured.
                  Sign in at <code className="bg-blue-100 px-1 rounded">/sign-in</code>
                </p>
              </div>
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-amber-100 text-amber-800">Supabase Auth</Badge>
                </div>
                <p className="text-sm text-amber-700">
                  Additional auth available via Supabase at <code className="bg-amber-100 px-1 rounded">localhost:3000</code>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
