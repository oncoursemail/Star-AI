--!strict
-- Safe server defaults for the sample last-player-standing arena.
return table.freeze({
	MinimumPlayers = 2,
	MaximumPlayers = 12,
	IntermissionSeconds = 12,
	PlayingSeconds = 90,
	ResultsSeconds = 5,
	WinnerCoins = 25,
})
