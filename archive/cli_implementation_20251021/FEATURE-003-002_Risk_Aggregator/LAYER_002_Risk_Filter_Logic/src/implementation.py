"""Risk Filter Logic implementation for filtering trades based on risk criteria."""

from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Enum for risk levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFilterError(Exception):
    """Base exception for risk filter errors."""
    pass


class InvalidInputError(RiskFilterError):
    """Exception raised for invalid input data."""
    pass


class ConfigurationError(RiskFilterError):
    """Exception raised for configuration errors."""
    pass


@dataclass
class Trade:
    """Trade data model."""
    id: str
    symbol: str
    quantity: float
    price: float
    timestamp: datetime
    account_id: str
    trade_type: str
    risk_score: Optional[float] = None


@dataclass
class RiskFilterConfig:
    """Configuration for risk filtering."""
    max_position_size: float = 100000.0
    max_daily_loss: float = 5000.0
    max_concentration: float = 0.2
    risk_score_threshold: float = 0.8
    enabled: bool = True


class RiskFilter:
    """Risk filter for evaluating and filtering trades based on risk criteria."""
    
    def __init__(self, config: Optional[RiskFilterConfig] = None):
        """
        Initialize risk filter with configuration.
        
        Args:
            config: Risk filter configuration. Uses defaults if not provided.
        """
        self.config = config or RiskFilterConfig()
        self.daily_positions: Dict[str, Dict[str, float]] = {}
        self.daily_pnl: Dict[str, float] = {}
        self._validate_config()
        logger.info("Risk filter initialized with config: %s", self.config)
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if self.config.max_position_size <= 0:
            raise ConfigurationError("max_position_size must be positive")
        if self.config.max_daily_loss <= 0:
            raise ConfigurationError("max_daily_loss must be positive")
        if not 0 < self.config.max_concentration <= 1:
            raise ConfigurationError("max_concentration must be between 0 and 1")
        if not 0 <= self.config.risk_score_threshold <= 1:
            raise ConfigurationError("risk_score_threshold must be between 0 and 1")
    
    def filter_trades(self, trades: List[Trade]) -> Tuple[List[Trade], List[Dict[str, Any]]]:
        """
        Filter trades based on risk criteria.
        
        Args:
            trades: List of trades to filter
            
        Returns:
            Tuple of (approved_trades, rejected_trades_with_reasons)
            
        Raises:
            InvalidInputError: If input data is invalid
        """
        if not self.config.enabled:
            logger.info("Risk filter is disabled, approving all trades")
            return trades, []
        
        if not isinstance(trades, list):
            raise InvalidInputError("trades must be a list")
        
        approved = []
        rejected = []
        
        for trade in trades:
            try:
                self._validate_trade(trade)
                rejection_reason = self._evaluate_trade(trade)
                
                if rejection_reason:
                    rejected.append({
                        'trade': trade,
                        'reason': rejection_reason,
                        'timestamp': datetime.now()
                    })
                    logger.warning("Trade %s rejected: %s", trade.id, rejection_reason)
                else:
                    approved.append(trade)
                    self._update_positions(trade)
                    logger.info("Trade %s approved", trade.id)
                    
            except Exception as e:
                rejected.append({
                    'trade': trade,
                    'reason': f"Validation error: {str(e)}",
                    'timestamp': datetime.now()
                })
                logger.error("Error processing trade %s: %s", getattr(trade, 'id', 'unknown'), str(e))
        
        return approved, rejected
    
    def _validate_trade(self, trade: Trade) -> None:
        """
        Validate trade data.
        
        Args:
            trade: Trade to validate
            
        Raises:
            InvalidInputError: If trade data is invalid
        """
        if not isinstance(trade, Trade):
            raise InvalidInputError("Invalid trade object")
        if not trade.id:
            raise InvalidInputError("Trade ID is required")
        if not trade.symbol:
            raise InvalidInputError("Trade symbol is required")
        if trade.quantity <= 0:
            raise InvalidInputError("Trade quantity must be positive")
        if trade.price <= 0:
            raise InvalidInputError("Trade price must be positive")
        if not trade.account_id:
            raise InvalidInputError("Account ID is required")
        if trade.trade_type not in ['BUY', 'SELL']:
            raise InvalidInputError("Trade type must be BUY or SELL")
    
    def _evaluate_trade(self, trade: Trade) -> Optional[str]:
        """
        Evaluate trade against risk criteria.
        
        Args:
            trade: Trade to evaluate
            
        Returns:
            Rejection reason if trade violates criteria, None if approved
        """
        # Check position size
        position_value = trade.quantity * trade.price
        if position_value > self.config.max_position_size:
            return f"Position size ${position_value:.2f} exceeds limit ${self.config.max_position_size:.2f}"
        
        # Check daily loss limit
        account_pnl = self.daily_pnl.get(trade.account_id, 0.0)
        if account_pnl < -self.config.max_daily_loss:
            return f"Daily loss ${-account_pnl:.2f} exceeds limit ${self.config.max_daily_loss:.2f}"
        
        # Check concentration
        account_positions = self.daily_positions.get(trade.account_id, {})
        total_exposure = sum(account_positions.values()) + position_value
        if total_exposure > 0:
            symbol_exposure = account_positions.get(trade.symbol, 0.0) + position_value
            concentration = symbol_exposure / total_exposure
            if concentration > self.config.max_concentration:
                return f"Symbol concentration {concentration:.2%} exceeds limit {self.config.max_concentration:.2%}"
        
        # Check risk score
        if trade.risk_score is not None and trade.risk_score > self.config.risk_score_threshold:
            return f"Risk score {trade.risk_score:.2f} exceeds threshold {self.config.risk_score_threshold:.2f}"
        
        return None
    
    def _update_positions(self, trade: Trade) -> None:
        """Update position tracking after trade approval."""
        if trade.account_id not in self.daily_positions:
            self.daily_positions[trade.account_id] = {}
        
        position_value = trade.quantity * trade.price
        if trade.trade_type == 'SELL':
            position_value = -position_value
        
        current_position = self.daily_positions[trade.account_id].get(trade.symbol, 0.0)
        self.daily_positions[trade.account_id][trade.symbol] = current_position + position_value
    
    def get_risk_metrics(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current risk metrics.
        
        Args:
            account_id: Optional account ID to get metrics for specific account
            
        Returns:
            Dictionary containing risk metrics
        """
        if account_id:
            positions = self.daily_positions.get(account_id, {})
            total_exposure = sum(abs(v) for v in positions.values())
            return {
                'account_id': account_id,
                'total_exposure': total_exposure,
                'positions': positions,
                'daily_pnl': self.daily_pnl.get(account_id, 0.0),
                'position_count': len(positions)
            }
        else:
            total_accounts = len(self.daily_positions)
            total_exposure = sum(
                sum(abs(v) for v in positions.values())
                for positions in self.daily_positions.values()
            )
            return {
                'total_accounts': total_accounts,
                'total_exposure': total_exposure,
                'total_positions': sum(len(p) for p in self.daily_positions.values())
            }
    
    def reset_daily_metrics(self) -> None:
        """Reset daily metrics (typically called at start of trading day)."""
        self.daily_positions.clear()
        self.daily_pnl.clear()
        logger.info("Daily risk metrics reset")
    
    def update_pnl(self, account_id: str, pnl_change: float) -> None:
        """
        Update P&L for an account.
        
        Args:
            account_id: Account identifier
            pnl_change: Change in P&L (positive for profit, negative for loss)
        """
        current_pnl = self.daily_pnl.get(account_id, 0.0)
        self.daily_pnl[account_id] = current_pnl + pnl_change
        logger.info("Updated P&L for account %s: %+.2f (total: %+.2f)", 
                   account_id, pnl_change, self.daily_pnl[account_id])


class RiskFilterService:
    """Service layer for risk filtering operations."""
    
    def __init__(self, config: Optional[RiskFilterConfig] = None):
        """
        Initialize risk filter service.
        
        Args:
            config: Risk filter configuration
        """
        self.risk_filter = RiskFilter(config)
        self.processing_stats = {
            'total_processed': 0,
            'total_approved': 0,
            'total_rejected': 0
        }
    
    def process_trade_batch(self, trades: List[Trade]) -> Dict[str, Any]:
        """
        Process a batch of trades through risk filter.
        
        Args:
            trades: List of trades to process
            
        Returns:
            Dictionary containing results and statistics
        """
        start_time = datetime.now()
        
        try:
            approved, rejected = self.risk_filter.filter_trades(trades)
            
            # Update statistics
            self.processing_stats['total_processed'] += len(trades)
            self.processing_stats['total_approved'] += len(approved)
            self.processing_stats['total_rejected'] += len(rejected)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': True,
                'approved_trades': approved,
                'rejected_trades': rejected,
                'statistics': {
                    'batch_size': len(trades),
                    'approved_count': len(approved),
                    'rejected_count': len(rejected),
                    'approval_rate': len(approved) / len(trades) if trades else 0,
                    'processing_time_seconds': processing_time
                },
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error("Error processing trade batch: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now()
            }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and statistics."""
        return {
            'status': 'operational',
            'config': {
                'enabled': self.risk_filter.config.enabled,
                'max_position_size': self.risk_filter.config.max_position_size,
                'max_daily_loss': self.risk_filter.config.max_daily_loss,
                'max_concentration': self.risk_filter.config.max_concentration,
                'risk_score_threshold': self.risk_filter.config.risk_score_threshold
            },
            'statistics': self.processing_stats.copy(),
            'risk_metrics': self.risk_filter.get_risk_metrics(),
            'timestamp': datetime.now()
        }


# Utility functions for integration
def create_trade(trade_data: Dict[str, Any]) -> Trade:
    """
    Create Trade object from dictionary.
    
    Args:
        trade_data: Dictionary containing trade data
        
    Returns:
        Trade object
        
    Raises:
        InvalidInputError: If required fields are missing
    """
    required_fields = ['id', 'symbol', 'quantity', 'price', 'account_id', 'trade_type']
    missing_fields = [f for f in required_fields if f not in trade_data]
    
    if missing_fields:
        raise InvalidInputError(f"Missing required fields: {missing_fields}")
    
    return Trade(
        id=trade_data['id'],
        symbol=trade_data['symbol'],
        quantity=float(trade_data['quantity']),
        price=float(trade_data['price']),
        timestamp=trade_data.get('timestamp', datetime.now()),
        account_id=trade_data['account_id'],
        trade_type=trade_data['trade_type'],
        risk_score=trade_data.get('risk_score')
    )


def calculate_risk_score(trade: Trade, market_data: Optional[Dict[str, Any]] = None) -> float:
    """
    Calculate risk score for a trade.
    
    Args:
        trade: Trade to score
        market_data: Optional market data for enhanced scoring
        
    Returns:
        Risk score between 0 and 1 (higher = riskier)
    """
    base_score = 0.0
    
    # Size-based risk
    position_value = trade.quantity * trade.price
    if position_value > 50000:
        base_score += 0.3
    elif position_value > 25000:
        base_score += 0.2
    elif position_value > 10000:
        base_score += 0.1
    
    # Market volatility (if data available)
    if market_data and 'volatility' in market_data:
        volatility = market_data['volatility']
        if volatility > 0.3:
            base_score += 0.3
        elif volatility > 0.2:
            base_score += 0.2
        elif volatility > 0.1:
            base_score += 0.1
    
    # Time-based risk (outside regular hours)
    hour = trade.timestamp.hour
    if hour < 9 or hour > 16:
        base_score += 0.2
    
    return min(base_score, 1.0)
