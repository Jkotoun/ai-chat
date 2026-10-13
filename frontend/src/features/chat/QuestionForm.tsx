import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import { useState, type FormEvent } from "react";
import { PILL_RADIUS } from "./styles";

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
    <Stack
      component="form"
      direction="row"
      spacing={1}
      onSubmit={submit}
      sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: "divider" }}
    >
      <TextField
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder="Ask a question…"
        size="small"
        fullWidth
        slotProps={{
          htmlInput: { "aria-label": "Question", maxLength: MAX_QUESTION_LENGTH },
          input: { sx: { borderRadius: PILL_RADIUS } },
        }}
      />
      <Button
        type="submit"
        variant="contained"
        disableElevation
        disabled={disabled || !trimmed}
        sx={{ borderRadius: PILL_RADIUS, px: 3 }}
      >
        Send
      </Button>
    </Stack>
  );
}
