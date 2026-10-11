import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

const SUGGESTIONS = [
  "What plans do you offer?",
  "How do I share a folder?",
  "Can I get a refund?",
  "How long do you keep deleted files?",
];

type EmptyStateProps = { onAsk: (question: string) => void };

export default function EmptyState({ onAsk }: EmptyStateProps) {
  return (
    <Stack spacing={2} sx={{ m: "auto", maxWidth: 440, alignItems: "center", textAlign: "center" }}>
      <Typography variant="h6">How can I help?</Typography>
      <Typography variant="body2" color="text.secondary">
        Ask about plans, billing, sharing, or our terms.
      </Typography>
      <Stack
        direction="row"
        useFlexGap
        spacing={1}
        sx={{ flexWrap: "wrap", justifyContent: "center" }}
      >
        {SUGGESTIONS.map((question) => (
          <Chip
            key={question}
            label={question}
            variant="outlined"
            onClick={() => onAsk(question)}
          />
        ))}
      </Stack>
    </Stack>
  );
}
