import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { inputStyles } from "@/components/ui/input";
import { useDebounced } from "@/hooks/useDebounced";
import { cn } from "@/lib/utils";

/** Campo de busca que só avisa o pai depois que a pessoa para de digitar. */
export function SearchBox({
  id,
  label,
  placeholder,
  onSearch,
  className,
}: {
  id: string;
  label: string;
  placeholder: string;
  onSearch: (term: string) => void;
  className?: string;
}) {
  const [text, setText] = useState("");
  const debounced = useDebounced(text.trim());
  const callback = useRef(onSearch);
  callback.current = onSearch;

  useEffect(() => {
    callback.current(debounced);
  }, [debounced]);

  return (
    <div className={cn("min-w-[200px] flex-1", className)}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">
        {label}
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" />
        <input
          id={id}
          type="search"
          value={text}
          maxLength={100}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          className={cn(inputStyles, "pl-9")}
        />
      </div>
    </div>
  );
}
