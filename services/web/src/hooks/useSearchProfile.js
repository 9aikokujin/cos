import { useState, useMemo } from "react";

export const useSearchProfiles = (profiles = [], searchKey) => {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredProfiles = useMemo(() => {
    if (!searchTerm.trim()) return profiles;

    const term = searchTerm.toLowerCase();
    return profiles.filter((profile) => String(profile[searchKey] || '')?.toLowerCase().includes(term));
  }, [profiles, searchTerm]);

  return {
    searchTerm,
    setSearchTerm,
    filteredProfiles,
    isEmptyResults: filteredProfiles.length === 0 && searchTerm.trim() !== "",
  };
};
