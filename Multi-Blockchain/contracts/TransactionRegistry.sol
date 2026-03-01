// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title TransactionRegistry
/// @notice On-chain registry for critical transactions on the settlement layer.
///         Records transaction hashes and metadata for immutable audit trails.
///         Only critical transactions (property registration, legal asset
///         transfers) are recorded here; operational data stays on L2.
contract TransactionRegistry {
    struct TxRecord {
        bytes32 payloadHash;
        address sender;
        uint256 registeredAt;
        bool exists;
    }

    mapping(bytes32 => TxRecord) public transactions;
    uint256 public transactionCount;

    address public owner;

    event TransactionRegistered(
        bytes32 indexed txIdHash,
        bytes32 indexed payloadHash,
        address indexed sender,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorised");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Register a critical transaction on the settlement layer.
    /// @param txIdHash Hash of the off-chain transaction ID.
    /// @param payloadHash Hash of the transaction payload.
    /// @param sender The original transaction sender.
    function registerTransaction(
        bytes32 txIdHash,
        bytes32 payloadHash,
        address sender
    ) external onlyOwner {
        require(!transactions[txIdHash].exists, "Transaction already registered");
        require(sender != address(0), "Zero sender");

        transactions[txIdHash] = TxRecord({
            payloadHash: payloadHash,
            sender: sender,
            registeredAt: block.timestamp,
            exists: true
        });

        transactionCount++;

        emit TransactionRegistered(txIdHash, payloadHash, sender, block.timestamp);
    }

    /// @notice Check whether a transaction has been registered.
    /// @param txIdHash Hash of the transaction ID to look up.
    /// @return exists Whether the transaction exists in the registry.
    /// @return payloadHash The payload hash if it exists.
    /// @return registeredAt The registration timestamp.
    function verifyTransaction(bytes32 txIdHash)
        external
        view
        returns (bool exists, bytes32 payloadHash, uint256 registeredAt)
    {
        TxRecord storage r = transactions[txIdHash];
        return (r.exists, r.payloadHash, r.registeredAt);
    }
}
