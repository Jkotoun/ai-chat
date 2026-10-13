import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ESCALATION_QUESTION } from "./messages";
import { PILL_RADIUS } from "./styles";

type ChatHeaderProps = { disabled: boolean; onAsk: (question: string) => void };

export default function ChatHeader({ disabled, onAsk }: ChatHeaderProps) {
  return (
    <Stack
      direction="row"
      spacing={1.5}
      sx={{
        alignItems: "center",
        px: 2,
        py: 1.5,
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Avatar sx={{ bgcolor: "primary.main", width: 36, height: 36, fontSize: 14 }}>AI</Avatar>
      <Stack sx={{ flex: 1 }}>
        <Typography variant="subtitle1" component="h1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
          AI support
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Answers from our FAQ and Terms of Service
        </Typography>
      </Stack>
      <Button
        variant="outlined"
        size="small"
        disabled={disabled}
        onClick={() => onAsk(ESCALATION_QUESTION)}
        sx={{ borderRadius: PILL_RADIUS, flexShrink: 0 }}
      >
        Talk to a human
      </Button>
    </Stack>
  );
}
