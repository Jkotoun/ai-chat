import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";

type TicketCardProps = { reference: string };

export default function TicketCard({ reference }: TicketCardProps) {
  return (
    <Alert severity="success" variant="outlined" sx={{ borderRadius: 3 }}>
      <AlertTitle>Support ticket {reference}</AlertTitle>
      Our support team will contact you by email.
    </Alert>
  );
}
