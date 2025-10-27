from datetime import datetime, timedelta
from typing import Union, Tuple, Optional
import calendar


class DateCalculator:
    """A class for performing various date calculations and manipulations."""
    
    def add_days(self, date: datetime, days: int) -> datetime:
        """
        Add a specified number of days to a given date.
        
        Args:
            date: The starting date
            days: Number of days to add (can be negative)
            
        Returns:
            The resulting date after adding the specified days
            
        Raises:
            TypeError: If date is not a datetime object or days is not an integer
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
        if not isinstance(days, int):
            raise TypeError("days must be an integer")
            
        return date + timedelta(days=days)
    
    def subtract_days(self, date: datetime, days: int) -> datetime:
        """
        Subtract a specified number of days from a given date.
        
        Args:
            date: The starting date
            days: Number of days to subtract
            
        Returns:
            The resulting date after subtracting the specified days
            
        Raises:
            TypeError: If date is not a datetime object or days is not an integer
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
        if not isinstance(days, int):
            raise TypeError("days must be an integer")
            
        return date - timedelta(days=days)
    
    def days_between(self, date1: datetime, date2: datetime) -> int:
        """
        Calculate the number of days between two dates.
        
        Args:
            date1: The first date
            date2: The second date
            
        Returns:
            The absolute number of days between the two dates
            
        Raises:
            TypeError: If either date is not a datetime object
        """
        if not isinstance(date1, datetime):
            raise TypeError("date1 must be a datetime object")
        if not isinstance(date2, datetime):
            raise TypeError("date2 must be a datetime object")
            
        delta = abs(date2 - date1)
        return delta.days
    
    def is_leap_year(self, year: int) -> bool:
        """
        Determine if a given year is a leap year.
        
        Args:
            year: The year to check
            
        Returns:
            True if the year is a leap year, False otherwise
            
        Raises:
            TypeError: If year is not an integer
            ValueError: If year is negative
        """
        if not isinstance(year, int):
            raise TypeError("year must be an integer")
        if year < 0:
            raise ValueError("year must be non-negative")
            
        return calendar.isleap(year)
    
    def get_weekday(self, date: datetime) -> str:
        """
        Get the day of the week for a given date.
        
        Args:
            date: The date to check
            
        Returns:
            The name of the weekday (e.g., 'Monday', 'Tuesday', etc.)
            
        Raises:
            TypeError: If date is not a datetime object
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
            
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                   'Friday', 'Saturday', 'Sunday']
        return weekdays[date.weekday()]
    
    def add_months(self, date: datetime, months: int) -> datetime:
        """
        Add a specified number of months to a given date.
        
        Args:
            date: The starting date
            months: Number of months to add (can be negative)
            
        Returns:
            The resulting date after adding the specified months
            
        Raises:
            TypeError: If date is not a datetime object or months is not an integer
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
        if not isinstance(months, int):
            raise TypeError("months must be an integer")
            
        # Calculate new year and month
        new_month = date.month + months
        new_year = date.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1
        
        # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
        max_day = calendar.monthrange(new_year, new_month)[1]
        new_day = min(date.day, max_day)
        
        return date.replace(year=new_year, month=new_month, day=new_day)
    
    def get_month_name(self, month: int) -> str:
        """
        Get the name of a month given its number.
        
        Args:
            month: Month number (1-12)
            
        Returns:
            The name of the month (e.g., 'January', 'February', etc.)
            
        Raises:
            TypeError: If month is not an integer
            ValueError: If month is not between 1 and 12
        """
        if not isinstance(month, int):
            raise TypeError("month must be an integer")
        if month < 1 or month > 12:
            raise ValueError("month must be between 1 and 12")
            
        return calendar.month_name[month]
    
    def get_quarter(self, date: datetime) -> int:
        """
        Get the quarter of the year for a given date.
        
        Args:
            date: The date to check
            
        Returns:
            The quarter number (1-4)
            
        Raises:
            TypeError: If date is not a datetime object
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
            
        return (date.month - 1) // 3 + 1
    
    def is_weekend(self, date: datetime) -> bool:
        """
        Check if a given date falls on a weekend.
        
        Args:
            date: The date to check
            
        Returns:
            True if the date is Saturday or Sunday, False otherwise
            
        Raises:
            TypeError: If date is not a datetime object
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
            
        return date.weekday() >= 5  # 5=Saturday, 6=Sunday
    
    def days_in_month(self, year: int, month: int) -> int:
        """
        Get the number of days in a specific month of a specific year.
        
        Args:
            year: The year
            month: The month (1-12)
            
        Returns:
            The number of days in the specified month
            
        Raises:
            TypeError: If year or month is not an integer
            ValueError: If month is not between 1 and 12 or year is negative
        """
        if not isinstance(year, int):
            raise TypeError("year must be an integer")
        if not isinstance(month, int):
            raise TypeError("month must be an integer")
        if year < 0:
            raise ValueError("year must be non-negative")
        if month < 1 or month > 12:
            raise ValueError("month must be between 1 and 12")
            
        return calendar.monthrange(year, month)[1]
    
    def next_business_day(self, date: datetime) -> datetime:
        """
        Get the next business day after the given date.
        
        Args:
            date: The starting date
            
        Returns:
            The next business day (Monday-Friday)
            
        Raises:
            TypeError: If date is not a datetime object
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
            
        next_day = date + timedelta(days=1)
        while next_day.weekday() >= 5:  # Skip weekends
            next_day += timedelta(days=1)
        return next_day
    
    def previous_business_day(self, date: datetime) -> datetime:
        """
        Get the previous business day before the given date.
        
        Args:
            date: The starting date
            
        Returns:
            The previous business day (Monday-Friday)
            
        Raises:
            TypeError: If date is not a datetime object
        """
        if not isinstance(date, datetime):
            raise TypeError("date must be a datetime object")
            
        prev_day = date - timedelta(days=1)
        while prev_day.weekday() >= 5:  # Skip weekends
            prev_day -= timedelta(days=1)
        return prev_day
