import { useAccountStore } from "@/app/store/entity/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import AccountsList from "@/components/accountsList/AccountsList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const AccountsPage = () => {
  useResetFiltersOnLeave()
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput store={useAccountStore} />
      </div>
      <AccountsList />
    </div>
  );
};

export default AccountsPage;
