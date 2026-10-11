import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { Source } from "@/client";

type SourceChipsProps = { sources: Source[] };

export default function SourceChips({ sources }: SourceChipsProps) {
  if (sources.length === 0) return null;
  return (
    <Stack
      direction="row"
      useFlexGap
      spacing={0.75}
      sx={{ flexWrap: "wrap", alignItems: "center" }}
    >
      <Typography variant="caption" color="text.secondary">
        Sources:
      </Typography>
      {sources.map((source) => (
        <Chip
          key={source.id}
          label={source.title}
          title={source.source}
          size="small"
          variant="outlined"
        />
      ))}
    </Stack>
  );
}
