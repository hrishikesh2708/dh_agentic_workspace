import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { JWT_COOKIE } from "@/lib/auth";

export default async function HomePage() {
  const store = await cookies();
  const token = store.get(JWT_COOKIE)?.value;
  if (token) {
    redirect("/chat");
  }
  redirect("/login");
}
