class RiskManager:
    @staticmethod
    def position_size(capital, risk_per_trade=0.02, stop_loss_pct=0.05):
        return capital * risk_per_trade / stop_loss_pct
    @staticmethod
    def stop_loss(entry_price, current_price, stop_loss_pct=0.05):
        return current_price <= entry_price * (1 - stop_loss_pct)
