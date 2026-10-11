import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import { keyframes } from "@mui/material/styles";

const DOT_DELAYS_MS = [0, 150, 300];

const bounce = keyframes`
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
`;

export default function TypingDots() {
  return (
    <Stack direction="row" spacing={0.5} sx={{ py: 1 }} role="status" aria-label="Thinking">
      {DOT_DELAYS_MS.map((delay) => (
        <Box
          key={delay}
          sx={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            bgcolor: "text.secondary",
            animation: `${bounce} 1s ease-in-out ${delay}ms infinite`,
          }}
        />
      ))}
    </Stack>
  );
}
