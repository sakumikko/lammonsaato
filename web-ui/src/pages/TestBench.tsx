import { useState, useCallback, useEffect } from 'react';
import { SchedulePanel } from '@/components/heating/SchedulePanel';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScheduleState, ScheduleParameters } from '@/types/heating';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { ThemeToggle } from '@/components/ThemeToggle';
import {
  FlaskConical,
  Clock,
  Sun,
  Moon,
  Server,
  Code,
  RefreshCw,
  Zap,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useMockServer, PriceScenario } from '@/hooks/useMockServer';

// ============================================
// LOCAL MOCK MODE (Fallback without server)
// ============================================

const createLocalMockSchedule = (params: ScheduleParameters): ScheduleState => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);

  const blocks = [];
  const targetMinutes = params.totalHours * 60;

  if (targetMinutes === 0) {
    return {
      blocks: [],
      nordpoolAvailable: true,
      currentPrice: 3.5,
      scheduledMinutes: 0,
      parameters: params,
    };
  }

  let remainingMinutes = targetMinutes;
  const blockDurations: number[] = [];

  while (remainingMinutes > 0 && blockDurations.length < 10) {
    let duration: number;
    if (remainingMinutes >= params.maxBlockDuration) {
      duration = params.maxBlockDuration;
    } else if (remainingMinutes >= params.minBlockDuration) {
      duration = remainingMinutes;
    } else {
      if (blockDurations.length === 0) {
        duration = params.minBlockDuration;
      } else {
        break;
      }
    }
    blockDurations.push(duration);
    remainingMinutes -= duration;
  }

  let currentMinutes = 21 * 60;

  for (let i = 0; i < blockDurations.length; i++) {
    const duration = blockDurations[i];
    const startTotalMinutes = currentMinutes;
    const startHour = Math.floor(startTotalMinutes / 60) % 24;
    const startMin = startTotalMinutes % 60;
    const endTotalMinutes = startTotalMinutes + duration;
    const endHour = Math.floor(endTotalMinutes / 60) % 24;
    const endMin = endTotalMinutes % 60;
    const isEndNextDay = endTotalMinutes >= 24 * 60;

    const startTime = `${String(startHour).padStart(2, '0')}:${String(startMin).padStart(2, '0')}`;
    const endTime = `${String(endHour).padStart(2, '0')}:${String(endMin).padStart(2, '0')}`;

    const blockDate = isEndNextDay ? tomorrow : today;
    const endDateTime = new Date(blockDate);
    endDateTime.setHours(endHour, endMin, 0, 0);

    blocks.push({
      start: startTime,
      end: endTime,
      endDateTime: endDateTime.toISOString(),
      price: 1.5 + i * 0.8,
      duration,
      enabled: true,
    });

    currentMinutes = endTotalMinutes + duration;
  }

  const actualTotalMinutes = blockDurations.reduce((sum, d) => sum + d, 0);

  return {
    blocks,
    nordpoolAvailable: true,
    currentPrice: 3.5,
    scheduledMinutes: actualTotalMinutes,
    parameters: params,
  };
};

// ============================================
// SCENARIO LABELS
// ============================================

const SCENARIO_LABELS: Record<PriceScenario, string> = {
  typical_winter: 'Typical Winter Night',
  cheap_night: 'Cheap Night (Low Demand)',
  expensive_night: 'Expensive Night (Cold Snap)',
  negative_prices: 'Negative Prices (High Wind)',
  flat_prices: 'Flat Prices (Stable)',
  volatile: 'Volatile Prices',
  custom: 'Custom Prices',
};

// ============================================
// MAIN COMPONENT
// ============================================

type TestMode = 'server' | 'local';

const TestBench = () => {
  const { t } = useTranslation();

  // Mode selection
  const [mode, setMode] = useState<TestMode>('server');

  // Mock server hook
  const mockServer = useMockServer();

  // Local mock state (fallback)
  const [localParams, setLocalParams] = useState<ScheduleParameters>({
    minBlockDuration: 30,
    maxBlockDuration: 45,
    totalHours: 2,
  });
  const [localSchedule, setLocalSchedule] = useState<ScheduleState>(() =>
    createLocalMockSchedule(localParams)
  );
  const [localSimulatedTime, setLocalSimulatedTime] = useState<'day' | 'night'>('day');

  // Auto-switch to local mode if server not available
  useEffect(() => {
    if (mockServer.error && mode === 'server') {
      // Don't auto-switch, let user see the error and try to start server
    }
  }, [mockServer.error, mode]);

  // Calculate initial schedule when server connects
  useEffect(() => {
    if (mockServer.connected && !mockServer.schedule?.blocks.length) {
      mockServer.recalculateSchedule();
    }
  }, [mockServer.connected]);

  // Current state based on mode
  const schedule = mode === 'server' ? mockServer.schedule : localSchedule;
  const isInHeatingWindow =
    mode === 'server' ? mockServer.isInHeatingWindow : localSimulatedTime === 'night';
  const nightComplete = mode === 'server' ? mockServer.nightComplete : false;
  const params =
    mode === 'server'
      ? mockServer.schedule?.parameters || localParams
      : localParams;

  // Handlers based on mode
  const handleBlockEnabledChange = useCallback(
    async (blockNumber: number, enabled: boolean) => {
      if (mode === 'server') {
        await mockServer.setBlockEnabled(blockNumber, enabled);
      } else {
        setLocalSchedule((s) => ({
          ...s,
          blocks: s.blocks.map((b, i) => (i === blockNumber - 1 ? { ...b, enabled } : b)),
        }));
      }
    },
    [mode, mockServer]
  );

  const handleSaveAndRecalc = useCallback(
    async (newParams: ScheduleParameters) => {
      if (mode === 'server') {
        await mockServer.setScheduleParameters(newParams);
        await mockServer.recalculateSchedule();
      } else {
        await new Promise((resolve) => setTimeout(resolve, 500));
        setLocalParams(newParams);
        await new Promise((resolve) => setTimeout(resolve, 300));
        setLocalSchedule(createLocalMockSchedule(newParams));
      }
    },
    [mode, mockServer]
  );

  const handleRecalculate = useCallback(async () => {
    if (mode === 'server') {
      await mockServer.recalculateSchedule();
    } else {
      await new Promise((resolve) => setTimeout(resolve, 800));
      setLocalSchedule(createLocalMockSchedule(localParams));
    }
  }, [mode, mockServer, localParams]);

  // Handle scenario change
  const handleScenarioChange = useCallback(
    async (scenario: PriceScenario) => {
      if (mode === 'server') {
        await mockServer.setScenario(scenario);
      }
    },
    [mode, mockServer]
  );

  // Handle time simulation
  const handleTimeSimulation = useCallback(
    async (isNight: boolean) => {
      if (mode === 'server') {
        await mockServer.simulateTime(isNight ? 22 : 12);
      } else {
        setLocalSimulatedTime(isNight ? 'night' : 'day');
      }
    },
    [mode, mockServer]
  );

  return (
    <div className="min-h-screen bg-background bg-grid">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-warning/20">
                <FlaskConical className="w-6 h-6 text-warning" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">E2E Test Bench</h1>
                <p className="text-xs text-muted-foreground">
                  {mode === 'server' ? 'Real Algorithm via Mock Server' : 'Local Mock Data'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Mode Toggle */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50">
                <Button
                  variant={mode === 'server' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setMode('server')}
                  className="h-7 px-2"
                >
                  <Server className="w-3 h-3 mr-1" />
                  Server
                </Button>
                <Button
                  variant={mode === 'local' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setMode('local')}
                  className="h-7 px-2"
                >
                  <Code className="w-3 h-3 mr-1" />
                  Local
                </Button>
              </div>

              <Link to="/">
                <Button variant="outline" size="sm">
                  ← Back
                </Button>
              </Link>
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">
        {/* Server Status Banner */}
        {mode === 'server' && (
          <div
            className={`mb-6 p-4 rounded-lg flex items-center justify-between ${
              mockServer.connected
                ? 'bg-success/10 border border-success/30'
                : 'bg-destructive/10 border border-destructive/30'
            }`}
          >
            <div className="flex items-center gap-3">
              {mockServer.connected ? (
                <CheckCircle2 className="w-5 h-5 text-success" />
              ) : (
                <AlertCircle className="w-5 h-5 text-destructive" />
              )}
              <div>
                <div className="font-medium">
                  {mockServer.connected ? 'Mock Server Connected' : 'Mock Server Not Running'}
                </div>
                <div className="text-sm text-muted-foreground">
                  {mockServer.connected
                    ? 'Using real Python algorithm for schedule calculation'
                    : mockServer.error || 'Start with: python -m scripts.mock_server'}
                </div>
              </div>
            </div>
            {mockServer.connected && (
              <Badge variant="outline" className="font-mono">
                ws://localhost:8765
              </Badge>
            )}
          </div>
        )}

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Schedule Panel */}
          <div>
            {schedule && (
              <SchedulePanel
                schedule={schedule}
                nightComplete={nightComplete}
                onBlockEnabledChange={handleBlockEnabledChange}
                onScheduleParametersChange={handleSaveAndRecalc}
                onRecalculate={handleRecalculate}
                isInHeatingWindow={isInHeatingWindow}
              />
            )}
          </div>

          {/* Test Controls */}
          <div className="space-y-6">
            {/* Price Scenario (Server mode only) */}
            {mode === 'server' && mockServer.connected && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="w-5 h-5" />
                    Price Scenario
                  </CardTitle>
                  <CardDescription>
                    Test different electricity price patterns
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Select
                    value={mockServer.currentScenario}
                    onValueChange={(v) => handleScenarioChange(v as PriceScenario)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {mockServer.availableScenarios.map((scenario) => (
                        <SelectItem key={scenario} value={scenario}>
                          {SCENARIO_LABELS[scenario]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-3">
                    Changing scenario recalculates the schedule using the real optimization
                    algorithm.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Time Simulation */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Time Simulation
                </CardTitle>
                <CardDescription>
                  Simulate day/night to test the 21:00+ warning modal
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-4">
                  <Button
                    variant={!isInHeatingWindow ? 'default' : 'outline'}
                    onClick={() => handleTimeSimulation(false)}
                    className="flex-1"
                  >
                    <Sun className="w-4 h-4 mr-2" />
                    Daytime
                  </Button>
                  <Button
                    variant={isInHeatingWindow ? 'default' : 'outline'}
                    onClick={() => handleTimeSimulation(true)}
                    className="flex-1"
                  >
                    <Moon className="w-4 h-4 mr-2" />
                    Night
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground mt-4">
                  {isInHeatingWindow
                    ? 'Heating window is ACTIVE. Saving parameters will show a warning.'
                    : 'Heating window is NOT active. Parameters will be saved immediately.'}
                </p>
              </CardContent>
            </Card>

            {/* Current State Display */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  Current State
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRecalculate}
                    className="h-7 px-2"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    Recalc
                  </Button>
                </CardTitle>
                <CardDescription>Live view of schedule state</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 font-mono text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Mode:</span>
                    <Badge variant={mode === 'server' ? 'default' : 'secondary'}>
                      {mode === 'server' ? 'Real Algorithm' : 'Local Mock'}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Parameters:</span>
                    <span>
                      {params.minBlockDuration}/{params.maxBlockDuration}min, {params.totalHours}h
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Blocks:</span>
                    <span>{schedule?.blocks.length ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Scheduled:</span>
                    <span>{schedule?.scheduledMinutes ?? 0} min</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Enabled blocks:</span>
                    <span>{schedule?.blocks.filter((b) => b.enabled).length ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Current price:</span>
                    <span>{(schedule?.currentPrice ?? 0).toFixed(2)} c/kWh</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Quick Presets */}
            <Card>
              <CardHeader>
                <CardTitle>Quick Presets</CardTitle>
                <CardDescription>Test different parameter combinations</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: 'Default (30/45, 2h)', p: { minBlockDuration: 30, maxBlockDuration: 45, totalHours: 2 } },
                    { label: 'Long (45/60, 3h)', p: { minBlockDuration: 45, maxBlockDuration: 60, totalHours: 3 } },
                    { label: 'Short (30/30, 1h)', p: { minBlockDuration: 30, maxBlockDuration: 30, totalHours: 1 } },
                    { label: 'Maximum (60/60, 5h)', p: { minBlockDuration: 60, maxBlockDuration: 60, totalHours: 5 } },
                    { label: 'Disabled (0h)', p: { minBlockDuration: 30, maxBlockDuration: 45, totalHours: 0 } },
                    { label: 'Invalid (60/30)', p: { minBlockDuration: 60, maxBlockDuration: 30, totalHours: 2 } },
                  ].map(({ label, p }) => (
                    <Button
                      key={label}
                      variant="outline"
                      size="sm"
                      onClick={() => handleSaveAndRecalc(p)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Server Actions (Server mode only) */}
            {mode === 'server' && mockServer.connected && (
              <Card>
                <CardHeader>
                  <CardTitle>Server Actions</CardTitle>
                  <CardDescription>Control the mock server state</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => mockServer.resetState()}
                      className="flex-1"
                    >
                      Reset State
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => mockServer.recalculateSchedule()}
                      className="flex-1"
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Force Recalc
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default TestBench;
