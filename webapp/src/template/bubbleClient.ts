import type { DeviceInfo } from '../types';

import { BubbleWebApp } from '../../../../jeejio-bubble/sdk/WebApp.js';
import PixelMugModule from '../../../../jeejio-bubble/devices/PixelMug_1.1.js';

type PixelMugInstance = {
  rpc: {
    call(method: string, params: Record<string, unknown>): { method: string; params: Record<string, unknown> };
    talMpyExecOneScript(params: {
      id: string;
      version: string;
    }): { method: string; params: Record<string, unknown> };
  };
};

export type DeviceEventItem = {
  method?: string;
  name?: string;
  params?: {
    value?: unknown;
  };
};

export type DeviceEventPayload = {
  payload?: {
    device?: DeviceInfo;
    events?: DeviceEventItem[];
  };
};

const PixelMug = PixelMugModule as unknown as { new (): PixelMugInstance };
const pixelMugSdk = new PixelMug();
let webapp: BubbleWebApp | null = null;

export function hasJeeWebBridge() {
  return Boolean((globalThis as { JeeWeb?: unknown }).JeeWeb);
}

export function getWebApp() {
  if (!webapp) {
    webapp = new BubbleWebApp({
      debug: import.meta.env.DEV,
      timeoutMillis: 20000,
    });
  }

  return webapp;
}

export function getPixelMugSdk() {
  return pixelMugSdk;
}

export async function loadPixelMug() {
  if (!hasJeeWebBridge()) {
    return {
      name: 'PixelMug Mock',
      talId: 'PixelMug',
      slotId: 'mock-slot',
      online: true,
    } satisfies DeviceInfo;
  }

  const devices = (await getWebApp().getDevices()) as DeviceInfo[];
  return (
    devices.find((device) => device.talId === 'PixelMug') ||
    devices.find((device) => /pixelmug/i.test(device.name || '')) ||
    null
  );
}

export async function subscribePixelMugEvents(device: DeviceInfo) {
  if (!hasJeeWebBridge()) return;
  await getWebApp().subscribeDeviceEvents(device);
}

export function onPixelMugEvent(handler: (event: DeviceEventPayload) => void) {
  if (!hasJeeWebBridge()) return () => undefined;
  getWebApp().onDeviceEvent((event: unknown) => handler(event as DeviceEventPayload));
  return () => undefined;
}
