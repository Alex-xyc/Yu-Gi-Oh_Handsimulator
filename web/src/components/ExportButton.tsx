// "Export to Excel": runs an export (which downloads an .xlsx) and shows a spinner meanwhile

import Button from "@mui/material/Button";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Spinner } from "./common";

export function ExportButton({ onExport, disabled = false, onError }: {
  onExport: () => Promise<void>;
  disabled?: boolean;
  onError: (message: string) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await onExport();
    } catch (e) {
      onError(e instanceof Error ? t("exportButton.failedWith", { message: e.message }) : t("exportButton.failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="outlined" color="inherit" size="small" onClick={run} disabled={disabled || busy}
            className="min-w-[132px]">
      {busy ? <Spinner /> : t("exportButton.label")}
    </Button>
  );
}
