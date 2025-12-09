import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  useEntityBrowser,
  EntityInfo,
  EntityDomain,
  EntityValueType,
  TimeRangeHours,
  EntityHistoryData,
} from '@/hooks/useEntityBrowser';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Search,
  RefreshCw,
  ArrowLeft,
  Clock,
  Hash,
  ToggleLeft,
  Calendar,
  Type,
  TrendingUp,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const DOMAIN_OPTIONS: { value: EntityDomain | 'all'; label: string }[] = [
  { value: 'all', label: 'All Domains' },
  { value: 'sensor', label: 'Sensors' },
  { value: 'input_number', label: 'Input Numbers' },
  { value: 'input_boolean', label: 'Input Booleans' },
  { value: 'input_datetime', label: 'Input Datetimes' },
  { value: 'input_text', label: 'Input Texts' },
  { value: 'binary_sensor', label: 'Binary Sensors' },
  { value: 'switch', label: 'Switches' },
  { value: 'number', label: 'Numbers' },
];

const VALUE_TYPE_OPTIONS: { value: EntityValueType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Types' },
  { value: 'numeric', label: 'Numeric' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'datetime', label: 'DateTime' },
  { value: 'string', label: 'String' },
];

const TIME_RANGE_OPTIONS: { value: TimeRangeHours; label: string }[] = [
  { value: 1, label: '1 hour' },
  { value: 6, label: '6 hours' },
  { value: 24, label: '24 hours' },
  { value: 48, label: '48 hours' },
  { value: 168, label: '7 days' },
];

function getValueTypeIcon(type: EntityValueType) {
  switch (type) {
    case 'numeric':
      return <Hash className="h-3 w-3" />;
    case 'boolean':
      return <ToggleLeft className="h-3 w-3" />;
    case 'datetime':
      return <Calendar className="h-3 w-3" />;
    case 'string':
      return <Type className="h-3 w-3" />;
    default:
      return null;
  }
}

function formatValue(entity: EntityInfo): string {
  if (entity.state === 'unavailable' || entity.state === 'unknown') {
    return entity.state;
  }

  switch (entity.valueType) {
    case 'numeric':
      const num = parseFloat(entity.state);
      const formatted = Number.isInteger(num) ? num.toString() : num.toFixed(2);
      return entity.unit ? `${formatted} ${entity.unit}` : formatted;
    case 'boolean':
      return entity.state === 'on' ? 'On' : 'Off';
    case 'datetime':
      return entity.state;
    default:
      return entity.state;
  }
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(date: Date): string {
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface EntityHistoryModalProps {
  entity: EntityInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fetchHistory: (entityId: string, hours: TimeRangeHours) => Promise<EntityHistoryData>;
}

function EntityHistoryModal({ entity, open, onOpenChange, fetchHistory }: EntityHistoryModalProps) {
  const [timeRange, setTimeRange] = useState<TimeRangeHours>(24);
  const [historyData, setHistoryData] = useState<EntityHistoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!entity) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory(entity.entityId, timeRange);
      setHistoryData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  }, [entity, timeRange, fetchHistory]);

  // Load history when modal opens or time range changes
  useState(() => {
    if (open && entity) {
      loadHistory();
    }
  });

  // Reset and load when entity changes
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && entity) {
      loadHistory();
    } else {
      setHistoryData(null);
    }
    onOpenChange(newOpen);
  };

  const handleTimeRangeChange = (value: string) => {
    setTimeRange(parseInt(value) as TimeRangeHours);
    if (entity) {
      setLoading(true);
      fetchHistory(entity.entityId, parseInt(value) as TimeRangeHours)
        .then(setHistoryData)
        .catch(err => setError(err.message))
        .finally(() => setLoading(false));
    }
  };

  const isNumeric = entity?.valueType === 'numeric';
  const chartData = historyData?.points
    .filter(p => p.numericValue !== null)
    .map(p => ({
      time: p.timestamp.getTime(),
      value: p.numericValue,
      label: formatDateTime(p.timestamp),
    })) || [];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            {entity?.friendlyName || entity?.entityId}
          </DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-4 mb-4">
          <Select value={timeRange.toString()} onValueChange={handleTimeRangeChange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIME_RANGE_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value.toString()}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" size="sm" onClick={loadHistory} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4 mr-1", loading && "animate-spin")} />
            Refresh
          </Button>

          {historyData?.stats && (
            <div className="flex gap-4 text-sm text-muted-foreground ml-auto">
              <span>Min: <span className="text-foreground font-mono">{historyData.stats.min.toFixed(2)}</span></span>
              <span>Max: <span className="text-foreground font-mono">{historyData.stats.max.toFixed(2)}</span></span>
              <span>Avg: <span className="text-foreground font-mono">{historyData.stats.mean.toFixed(2)}</span></span>
            </div>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="text-destructive text-center py-8">{error}</div>
        )}

        {!loading && !error && historyData && (
          <>
            {/* Chart for numeric values */}
            {isNumeric && chartData.length > 0 && (
              <div className="h-64 mb-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="time"
                      type="number"
                      domain={['dataMin', 'dataMax']}
                      tickFormatter={(ts) => formatTime(new Date(ts))}
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      domain={['auto', 'auto']}
                      tickFormatter={(v) => v.toFixed(1)}
                    />
                    <Tooltip
                      labelFormatter={(ts) => formatDateTime(new Date(ts as number))}
                      formatter={(value: number) => [
                        `${value.toFixed(2)}${entity?.unit ? ` ${entity.unit}` : ''}`,
                        'Value'
                      ]}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="value"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* History table */}
            <ScrollArea className="flex-1 min-h-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-48">Timestamp</TableHead>
                    <TableHead>Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historyData.points.slice().reverse().slice(0, 100).map((point, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-sm">
                        {formatDateTime(point.timestamp)}
                      </TableCell>
                      <TableCell className="font-mono">
                        {point.value !== null ? String(point.value) : '-'}
                        {entity?.unit && point.numericValue !== null && ` ${entity.unit}`}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {historyData.points.length > 100 && (
                <p className="text-center text-sm text-muted-foreground py-2">
                  Showing last 100 of {historyData.points.length} records
                </p>
              )}
            </ScrollArea>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function EntityBrowser() {
  const {
    filteredEntities,
    loading,
    error,
    searchQuery,
    setSearchQuery,
    domainFilter,
    setDomainFilter,
    valueTypeFilter,
    setValueTypeFilter,
    refetch,
    fetchHistory,
  } = useEntityBrowser();

  const [selectedEntity, setSelectedEntity] = useState<EntityInfo | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);

  const handleEntityClick = (entity: EntityInfo) => {
    setSelectedEntity(entity);
    setHistoryModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center gap-4">
            <Link to="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            </Link>
            <h1 className="text-xl font-semibold">Entity Browser</h1>
            <div className="ml-auto text-sm text-muted-foreground">
              {filteredEntities.length} entities
            </div>
          </div>
        </div>
      </header>

      {/* Filters */}
      <div className="border-b bg-card/30">
        <div className="container mx-auto px-4 py-3">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            <Select value={domainFilter} onValueChange={(v) => setDomainFilter(v as EntityDomain | 'all')}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Domain" />
              </SelectTrigger>
              <SelectContent>
                {DOMAIN_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={valueTypeFilter} onValueChange={(v) => setValueTypeFilter(v as EntityValueType | 'all')}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                {VALUE_TYPE_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button variant="outline" size="icon" onClick={refetch} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="container mx-auto px-4 py-4">
        {loading && !filteredEntities.length && (
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-8 text-destructive">
            <p>{error}</p>
            <Button variant="outline" className="mt-4" onClick={refetch}>
              Try Again
            </Button>
          </div>
        )}

        {!loading && !error && filteredEntities.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No entities found
          </div>
        )}

        {filteredEntities.length > 0 && (
          <div className="space-y-1">
            {filteredEntities.map((entity) => (
              <div
                key={entity.entityId}
                className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 cursor-pointer transition-colors"
                onClick={() => handleEntityClick(entity)}
              >
                {/* Value type icon */}
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted">
                  {getValueTypeIcon(entity.valueType)}
                </div>

                {/* Entity info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{entity.friendlyName}</span>
                    {entity.valueType === 'numeric' && (
                      <TrendingUp className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground font-mono truncate">
                    {entity.entityId}
                  </div>
                </div>

                {/* Domain badge */}
                <Badge variant="outline" className="hidden sm:flex">
                  {entity.domain}
                </Badge>

                {/* Current value */}
                <div className="text-right min-w-[100px]">
                  <div className={cn(
                    "font-mono font-medium",
                    entity.state === 'unavailable' && "text-muted-foreground",
                    entity.valueType === 'boolean' && entity.state === 'on' && "text-green-500",
                    entity.valueType === 'boolean' && entity.state === 'off' && "text-muted-foreground",
                  )}>
                    {formatValue(entity)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatTime(entity.lastUpdated)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* History Modal */}
      <EntityHistoryModal
        entity={selectedEntity}
        open={historyModalOpen}
        onOpenChange={setHistoryModalOpen}
        fetchHistory={fetchHistory}
      />
    </div>
  );
}

export default EntityBrowser;
