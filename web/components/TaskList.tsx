import type { Task } from "@/types/estate";

export function TaskList({ tasks }: { tasks: Task[] }) {
  return (
    <section>
      <h2 className="text-lg font-semibold">Tasks</h2>
      <ul className="mt-3 divide-y rounded-md border bg-white">
        {tasks.map((task) => (
          <li key={task.id} className="flex items-center justify-between p-3 text-sm">
            <span>{task.title}</span>
            <span className="text-slate-500">{task.status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

