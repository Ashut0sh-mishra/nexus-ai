import { useCallback } from "react";
import { api } from "../utils/api.js";

export function useExport() {
  const exportPptx = useCallback(async (taskId, theme) => {
    const { data } = await api.post("/export/pptx", {
      task_id: taskId,
      theme,
    });
    return data;
  }, []);

  const exportPdf = useCallback(async (taskId, theme) => {
    const { data } = await api.post("/export/pdf", {
      task_id: taskId,
      theme,
    });
    return data;
  }, []);

  const createShare = useCallback(async (taskId) => {
    const { data } = await api.post("/share", { task_id: taskId });
    return data;
  }, []);

  return { exportPptx, exportPdf, createShare };
}
