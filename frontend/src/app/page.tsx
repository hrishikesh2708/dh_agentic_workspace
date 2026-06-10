import { redirect } from "next/navigation";
import { cookies } from "next/headers";

const JWT_COOKIE = "datahash_jwt";

export default async function HomePage() {
  const store = await cookies();
  const token = store.get(JWT_COOKIE)?.value;
  if (token) {
    redirect("/dashboard");
  }
  redirect("/login");
}
