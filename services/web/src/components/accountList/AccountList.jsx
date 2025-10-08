import AccountItem from "@/components/accountItem/AccountItem";

import "./AccountList.css";

const AccountList = ({ account, lastAccountElementRef }) => {
  return (
    <div className="account_list _flex_column_center">
      {account.map((item, index) => {
        if (account.length === index + 1) {
          return <AccountItem key={item.id} account={item} ref={lastAccountElementRef} />;
        }
        return <AccountItem key={item.id} account={item} />;
      })}
    </div>
  );
};

export default AccountList;
