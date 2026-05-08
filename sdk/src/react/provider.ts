import * as React from "react";
import { NexusClient } from "../client.js";
import type { NexusClientOptions } from "../types.js";

const Ctx = React.createContext<NexusClient | null>(null);

export interface NexusProviderProps extends NexusClientOptions {
  client?: NexusClient;
  children: React.ReactNode;
}

/**
 * Wrap your app once with `<NexusProvider baseUrl="https://api.foo.com" />`
 * to make a single shared `NexusClient` available to every hook below.
 */
export function NexusProvider({ children, client, ...opts }: NexusProviderProps) {
  const value = React.useMemo(
    () => client ?? new NexusClient(opts),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [client, opts.baseUrl, opts.token],
  );
  return React.createElement(Ctx.Provider, { value }, children);
}

/** Returns the active `NexusClient` (throws if no provider is mounted). */
export function useNexusClient(): NexusClient {
  const c = React.useContext(Ctx);
  if (!c) {
    throw new Error(
      "useNexusClient must be used inside <NexusProvider> (or pass a client explicitly).",
    );
  }
  return c;
}
