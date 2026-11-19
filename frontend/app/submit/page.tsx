import { SubmitForm } from "@/components/submit-form";

export const metadata = {
  title: "Report an issue · ChallengeMap",
};

export default function SubmitPage() {
  return (
    <div className="shell py-10 sm:py-14">
      <div className="max-w-2xl">
        <p className="eyebrow">Citizen report</p>
        <h1 className="h1 mt-2 text-3xl sm:text-4xl">Tell us what is not working</h1>
        <p className="lede mt-3">
          Write in Hindi, English or Hinglish. Before your report becomes a new challenge, we check
          whether someone nearby already reported the same problem — that is how the map stays
          honest instead of noisy.
        </p>
      </div>

      <SubmitForm />
    </div>
  );
}
