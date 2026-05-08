export { NexusProvider, useNexusClient } from "./provider.js";
export { useNexusGenerate, useNexusDeck } from "./hooks.js";
export { NexusSlide, NexusDeck } from "./NexusDeck.js";
export { PPTGenerator } from "./PPTGenerator.js";
export type { NexusProviderProps } from "./provider.js";
export type { NexusSlideProps, NexusDeckProps } from "./NexusDeck.js";
export type { UseNexusGenerateState } from "./hooks.js";
export type {
  PPTGeneratorProps,
  PPTGeneratorRenderApi,
} from "./PPTGenerator.js";
export type {
  Slide,
  SlideDeck,
  SlideLayout,
  GenerateOptions,
  GenerateResponse,
  TaskProgressEvent,
  UploadResponse,
} from "../types.js";
