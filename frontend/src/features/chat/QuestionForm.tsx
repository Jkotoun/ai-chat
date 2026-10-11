import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import { useState, type FormEvent } from "react";

// Matches the backend's ChatRequest limit.
const MAX_QUESTION_LENGTH = 2000;

type QuestionFormProps = { disabled: boolean; onAsk: (question: string) => void };

export default function QuestionForm({ disabled, onAsk }: QuestionFormProps) {
  const [question, setQuestion] = useState("");
  const trimmed = question.trim();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed) return;
    onAsk(trimmed);
    setQuestion("");
  }

  return (
    <Stack component="form" direction="row" spacing={1} onSubmit={submit}>
      <TextField
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder="Ask a question…"
        size="small"
        fullWidth
        slotProps={{ htmlInput: { "aria-label": "Question", maxLength: MAX_QUESTION_LENGTH } }}
      />
      <Button type="submit" variant="contained" disabled={disabled || !trimmed}>
        Send
      </Button>
    </Stack>
  );
}
