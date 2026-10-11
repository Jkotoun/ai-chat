import Typography from "@mui/material/Typography";
import ChatBubble from "./ChatBubble";
import type { Answer } from "./messages";

type AnswerProps = { answer: Answer };

function AnswerText({ answer }: AnswerProps) {
  if (answer.text) return <Typography sx={{ whiteSpace: "pre-wrap" }}>{answer.text}</Typography>;
  if (answer.status === "streaming") return <Typography color="text.secondary">…</Typography>;
  return null;
}

function Sources({ answer }: AnswerProps) {
  if (answer.sources.length === 0) return null;
  const titles = answer.sources.map((source) => source.title);
  return (
    <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
      Sources: {titles.join(" · ")}
    </Typography>
  );
}

export default function AssistantMessage({ answer }: AnswerProps) {
  return (
    <ChatBubble side="left" sx={{ bgcolor: "action.hover" }}>
      <AnswerText answer={answer} />
      {answer.error && (
        <Typography variant="body2" color="error">
          {answer.error}
        </Typography>
      )}
      <Sources answer={answer} />
    </ChatBubble>
  );
}
