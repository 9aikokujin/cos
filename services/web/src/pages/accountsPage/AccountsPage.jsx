import AccountsList from "@/components/accountsList/AccountsList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const AccountsPage = () => {
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput />
      </div>
      <AccountsList />
    </div>
  );
};

export default AccountsPage;
