/**
 * Home Assistant WebSocket API client
 *
 * Connects to HA via WebSocket for real-time entity state updates.
 * When running as an add-on, uses Supervisor token for auth.
 */

export interface HAEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
  last_updated: string;
}

export interface HAEvent {
  event_type: string;
  data: {
    entity_id: string;
    new_state: HAEntityState | null;
    old_state: HAEntityState | null;
  };
}

export interface StatisticsResult {
  start: string;
  end: string;
  sum?: number;
  mean?: number;
  min?: number;
  max?: number;
  state?: number;
  last_reset?: string;
}

type MessageHandler = (message: unknown) => void;
type StateChangeCallback = (entityId: string, state: HAEntityState) => void;
type ConnectionCallback = (connected: boolean) => void;

interface HAMessage {
  id?: number;
  type: string;
  [key: string]: unknown;
}

export class HAWebSocket {
  private ws: WebSocket | null = null;
  private messageId = 1;
  private pendingMessages: Map<number, MessageHandler> = new Map();
  private stateSubscribers: Set<StateChangeCallback> = new Set();
  private connectionSubscribers: Set<ConnectionCallback> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private url: string;
  private token: string;
  private isAuthenticated = false;

  constructor(url?: string, token?: string) {
    // When running as HA add-on, use Supervisor API
    // The add-on will inject these via environment or ingress
    this.url = url || this.getWebSocketUrl();
    this.token = token || this.getToken();
  }

  private getWebSocketUrl(): string {
    // Check for HA ingress (add-on mode)
    const ingressPath = (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__;
    if (ingressPath) {
      // Running as add-on via ingress
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}/api/websocket`;
    }

    // Development mode - connect to HA directly
    // Can be overridden via environment variable
    const haUrl = import.meta.env.VITE_HA_URL || 'http://homeassistant.local:8123';
    const wsProtocol = haUrl.startsWith('https') ? 'wss:' : 'ws:';
    const host = haUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
    return `${wsProtocol}//${host}/api/websocket`;
  }

  private getToken(): string {
    // Check for Supervisor token (add-on mode)
    const supervisorToken = (window as { __SUPERVISOR_TOKEN__?: string }).__SUPERVISOR_TOKEN__;
    if (supervisorToken) {
      return supervisorToken;
    }

    // Development mode - use long-lived access token
    return import.meta.env.VITE_HA_TOKEN || '';
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[HA WS] Connected');
          this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
          const message = JSON.parse(event.data);
          this.handleMessage(message, resolve, reject);
        };

        this.ws.onerror = (error) => {
          console.error('[HA WS] Error:', error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('[HA WS] Disconnected');
          this.isAuthenticated = false;
          this.notifyConnectionChange(false);
          this.scheduleReconnect();
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(message: HAMessage, resolveConnect?: () => void, rejectConnect?: (error: Error) => void) {
    switch (message.type) {
      case 'auth_required':
        this.sendAuth();
        break;

      case 'auth_ok':
        console.log('[HA WS] Authenticated');
        this.isAuthenticated = true;
        this.notifyConnectionChange(true);
        this.subscribeToStateChanges();
        resolveConnect?.();
        break;

      case 'auth_invalid':
        console.error('[HA WS] Authentication failed:', message.message);
        rejectConnect?.(new Error(message.message as string || 'Authentication failed'));
        break;

      case 'result':
        this.handleResult(message);
        break;

      case 'event':
        this.handleEvent(message);
        break;
    }
  }

  private sendAuth() {
    if (!this.token) {
      console.error('[HA WS] No authentication token available');
      return;
    }
    this.send({ type: 'auth', access_token: this.token });
  }

  private handleResult(message: HAMessage) {
    const handler = this.pendingMessages.get(message.id as number);
    if (handler) {
      this.pendingMessages.delete(message.id as number);
      handler(message);
    }
  }

  private handleEvent(message: HAMessage) {
    const event = message.event as HAEvent;
    if (event?.event_type === 'state_changed' && event.data.new_state) {
      const { entity_id, new_state } = event.data;
      this.stateSubscribers.forEach(callback => callback(entity_id, new_state));
    }
  }

  private subscribeToStateChanges() {
    this.sendCommand({ type: 'subscribe_events', event_type: 'state_changed' });
  }

  private send(message: HAMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private sendCommand(command: HAMessage): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const id = this.messageId++;
      const message = { ...command, id };

      this.pendingMessages.set(id, (result: unknown) => {
        const res = result as { success?: boolean; error?: { message: string }; result?: unknown };
        if (res.success === false) {
          reject(new Error(res.error?.message || 'Command failed'));
        } else {
          resolve(res.result);
        }
      });

      // Timeout after 10 seconds
      setTimeout(() => {
        if (this.pendingMessages.has(id)) {
          this.pendingMessages.delete(id);
          reject(new Error('Command timeout'));
        }
      }, 10000);

      this.send(message);
    });
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[HA WS] Max reconnection attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    console.log(`[HA WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }

  private notifyConnectionChange(connected: boolean) {
    this.connectionSubscribers.forEach(callback => callback(connected));
  }

  // Public API

  async getStates(): Promise<HAEntityState[]> {
    if (!this.isAuthenticated) {
      throw new Error('Not connected to Home Assistant');
    }
    return this.sendCommand({ type: 'get_states' }) as Promise<HAEntityState[]>;
  }

  async getState(entityId: string): Promise<HAEntityState | undefined> {
    const states = await this.getStates();
    return states.find(s => s.entity_id === entityId);
  }

  async callService(domain: string, service: string, data?: Record<string, unknown>): Promise<void> {
    if (!this.isAuthenticated) {
      throw new Error('Not connected to Home Assistant');
    }
    await this.sendCommand({
      type: 'call_service',
      domain,
      service,
      service_data: data,
    });
  }

  /**
   * Fetch statistics for entities over a time period
   * Uses the recorder/statistics_during_period API
   */
  async getStatistics(
    startTime: Date,
    endTime: Date,
    statisticIds: string[],
    period: '5minute' | 'hour' | 'day' | 'week' | 'month' = 'day'
  ): Promise<Record<string, StatisticsResult[]>> {
    if (!this.isAuthenticated) {
      throw new Error('Not connected to Home Assistant');
    }
    return this.sendCommand({
      type: 'recorder/statistics_during_period',
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      statistic_ids: statisticIds,
      period,
      types: ['sum', 'mean', 'min', 'max', 'state'],
    }) as Promise<Record<string, StatisticsResult[]>>;
  }

  /**
   * Fetch raw history for entities over a time period
   */
  async getHistory(
    startTime: Date,
    endTime: Date,
    entityIds: string[],
    minimalResponse: boolean = true
  ): Promise<HAEntityState[][]> {
    if (!this.isAuthenticated) {
      throw new Error('Not connected to Home Assistant');
    }
    return this.sendCommand({
      type: 'history/history_during_period',
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      entity_ids: entityIds,
      minimal_response: minimalResponse,
      significant_changes_only: false,
    }) as Promise<HAEntityState[][]>;
  }

  onStateChange(callback: StateChangeCallback): () => void {
    this.stateSubscribers.add(callback);
    return () => this.stateSubscribers.delete(callback);
  }

  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionSubscribers.add(callback);
    return () => this.connectionSubscribers.delete(callback);
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
    this.isAuthenticated = false;
  }

  get connected(): boolean {
    return this.isAuthenticated;
  }
}

// Singleton instance
let instance: HAWebSocket | null = null;

export function getHAWebSocket(): HAWebSocket {
  if (!instance) {
    instance = new HAWebSocket();
  }
  return instance;
}
