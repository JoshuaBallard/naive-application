import { server } from "@/lib/server";
import { InterviewForm } from "@/components/interview-form";

export const revalidate = 300;

export const metadata = { title: "Ask for the thirty minutes" };

export default async function Talk() {
  const { records } = await server.availability();
  const record = records[0];
  const windows = (record?.windows ?? []) as { id: string; label: string; timezone: string }[];
  const note = String(record?.booking_note ?? "");

  return (
    <div className="mx-auto max-w-3xl px-5 pb-10 pt-14">
      <p className="label mb-5">The only consequential action here</p>
      <h1 className="max-w-[20ch] text-[clamp(1.75rem,4.5vw,2.75rem)] leading-[1.1]">
        I think you two should talk
      </h1>

      <p className="prose-serif mt-6 text-body">
        This records a request. It does not book anything. Nothing is sent to a calendar,
        no invitation is created, and no email goes to anyone — there is no email provider
        in this system, which is also why your address never leaves the disk it is written
        to. Josh confirms by hand or not at all.
      </p>

      <p className="mt-6 max-w-[68ch] rounded-[3px] border border-rule bg-surface p-5 text-[14px] text-muted">
        {note}
      </p>

      <InterviewForm windows={windows} />
    </div>
  );
}
