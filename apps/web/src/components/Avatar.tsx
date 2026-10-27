import { roles } from "../store";
export default function Avatar({
  id,
  small = false,
}: {
  id: string;
  small?: boolean;
}) {
  const role = roles.find((a) => a.id === id) ?? roles[0];
  return (
    <span
      className={"avatar portrait-avatar " + (small ? "small" : "")}
      style={{ "--agent-color": role.color } as React.CSSProperties}
    >
      <img
        src={"/office/" + role.id + "-portrait.png"}
        alt=""
        draggable={false}
      />
    </span>
  );
}
