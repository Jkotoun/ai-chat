import Avatar from "@mui/material/Avatar";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function ChatHeader() {
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
      <Stack>
        <Typography variant="subtitle1" component="h1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
          AI support
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Answers from our FAQ and Terms of Service
        </Typography>
      </Stack>
    </Stack>
  );
}
